"""
shape_evolve — score TLA+ mutations against held-out Sherlock findings.

Wraps tools/spec_mutator.py (which generates + TLC-verifies novel
mutations) with the missing piece: coverage fitness on the 146
Sherlock-graded findings that have NO existing-shape RAG prior at cos>0.7.

This is the grounded-self-improvement loop for the shape library:
  1. spec_mutator.py generates novel mutations (already shipped)
  2. shape_evolve.py embeds each mutation's invariant + parent shape
     description and scores coverage on the 146 unmatched findings
  3. Top-ranked mutation = candidate to bank as next shape

Graph-level mutation (action_subdivide):
  Splits a payment action into pre/reenter/post atomic steps, exposing
  a reentrancy window.  See docs/architecture/SHAPE_GRAPH_MUTATIONS.md.

  Usage:
    python tools/shape_evolve.py --action-subdivide   # apply to all 9 specs

The fitness signal is SOUND (no LLM-as-judge):
  - TLC discharge yes/no (deterministic, by spec_mutator)
  - Cosine ≥ 0.7 to unmatched finding (deterministic, by embedding)
  - Anti-similarity: penalize variants whose centroid is within
    cos > 0.85 of any existing shape (otherwise they just rediscover
    the original)

Usage:
  python tools/shape_evolve.py [--score-only]       # score existing mutations
  python tools/shape_evolve.py --runs 20            # generate + score new ones
  python tools/shape_evolve.py --action-subdivide   # graph-level mutation
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, shutil
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent.parent
TLA_DIR = HERE / "docs" / "tla"
MUT_DIR = TLA_DIR / "mutations"
SHERLOCK_COVERAGE = HERE / "corpus" / "calibration" / "sherlock_coverage.jsonl"
COS_COVER = 0.7      # threshold: shape covers a finding
COS_ANTI = 0.85      # threshold: too-close-to-existing → penalty

# Variable names that signal "monetary/payment" semantics
_PAYMENT_NAMES = re.compile(
    r"paid|balance|transfer|payout|amount|fee|reward|claim|total",
    re.IGNORECASE,
)

# TLA2Tools jar (same path as spec_graph and spec_mutator expect)
TLA_JAR = str(TLA_DIR / "tla2tools.jar")


# ---------------------------------------------------------------------------
# action_subdivide: graph-level mutation operator
# ---------------------------------------------------------------------------

def _detect_payment_action(sg) -> Optional[dict]:
    """
    Find an action suitable for action_subdivide.

    Target pattern: parametric action A(param) that atomically writes to
    BOTH a 'payment variable' (paid_total, fee, etc.) AND a 'counter
    variable' (submissions, etc.) via function-update expressions of the
    form:  var' = [var EXCEPT ![param] = @ + Expr]

    Returns a dict with detection results, or None if not applicable.
    """
    g = sg.g
    variables = sg.variables

    for node, attrs in g.nodes(data=True):
        if attrs.get("kind") != "action":
            continue
        params = attrs.get("params", [])
        if not params:
            continue  # need parametric action
        param = params[0]
        body = attrs.get("body", "")

        # Find function-increment writes: var' = [var EXCEPT ![param] = @ + Expr]
        fn_inc: dict[str, str] = {}
        for var in variables:
            # Raw regex: /\ var' = [var EXCEPT ![param] = @ + ...rest-of-line]
            pat = (
                r"/\\"           # TLA+ conjunction /\
                r"\s+"
                + re.escape(var) + r"'\s*=\s*"
                + r"\[" + re.escape(var) + r"\s+EXCEPT\s+!\["
                + re.escape(param) + r"\]\s*=\s*@\s*\+\s*([^\n]+)"
            )
            m = re.search(pat, body)
            if m:
                fn_inc[var] = m.group(0).strip()  # full /\ line

        if len(fn_inc) < 2:
            continue

        # Classify: payment vs counter
        payment_var = next(
            (v for v in fn_inc if _PAYMENT_NAMES.search(v)), None
        )
        if payment_var is None:
            continue
        counter_candidates = [v for v in fn_inc if v != payment_var]
        if not counter_candidates:
            continue
        counter_var = counter_candidates[0]

        # Extract domain from `param \in Domain` guard in body
        dm = re.search(
            rf"\b{re.escape(param)}\s+\\in\s+([A-Za-z_]\w*)", body
        )
        if not dm:
            continue
        domain = dm.group(1)

        # Extract bound guard: counter_var[param] < MaxSomething
        bg = re.search(
            r"(/\\\s*" + re.escape(counter_var) + r"\[" + re.escape(param)
            + r"\]\s*<\s*\w+)",
            body,
        )
        bound_guard = bg.group(1).strip() if bg else None

        # Other variables that must be UNCHANGED in all three sub-actions
        other_vars = [v for v in variables if v not in fn_inc]

        return {
            "action_name": node,
            "param": param,
            "domain": domain,
            "payment_var": payment_var,
            "payment_line": fn_inc[payment_var],
            "counter_var": counter_var,
            "counter_line": fn_inc[counter_var],
            "bound_guard": bound_guard,
            "other_vars": other_vars,
            "scalar": False,
        }

    # Second pass: non-parametric actions with scalar-increment writes
    # (e.g. Uint64FeeOverflow.FinishRaffleBuggy)
    for node, attrs in g.nodes(data=True):
        if attrs.get("kind") != "action":
            continue
        if attrs.get("params"):
            continue  # parametric already handled above
        body = attrs.get("body", "")

        # Find scalar-increment writes: var' = var + Expr  (no EXCEPT)
        scalar_inc: dict[str, str] = {}
        for var in variables:
            pat = (
                r"/\\"
                r"\s+"
                + re.escape(var) + r"'\s*=\s*"
                + re.escape(var) + r"\s*\+\s*([^\n]+)"
            )
            m = re.search(pat, body)
            if m:
                scalar_inc[var] = m.group(0).strip()

        if len(scalar_inc) < 2:
            continue

        payment_var = next(
            (v for v in scalar_inc if _PAYMENT_NAMES.search(v)), None
        )
        if payment_var is None:
            continue
        counter_candidates = [v for v in scalar_inc if v != payment_var]
        counter_var = counter_candidates[0]

        # Bound guard: counter_var < MaxSomething
        bg = re.search(
            r"(/\\\s*" + re.escape(counter_var) + r"\s*<\s*\w+)",
            body,
        )
        bound_guard = bg.group(1).strip() if bg else None

        # Other variables (may include vars with complex writes not captured above)
        other_vars = [v for v in variables if v not in scalar_inc]

        return {
            "action_name": node,
            "param": None,
            "domain": None,
            "payment_var": payment_var,
            "payment_line": scalar_inc[payment_var],
            "counter_var": counter_var,
            "counter_line": scalar_inc[counter_var],
            "bound_guard": bound_guard,
            "other_vars": other_vars,
            "scalar": True,
        }

    return None


def _add_variable_to_block(vars_text: str, new_var: str,
                            domain: Optional[str]) -> str:
    """
    Add *new_var* to a VARIABLES block and update the vars == <<...>> tuple.
    Inserts the new variable after the last existing variable, adding a
    comma to the previous last variable.
    domain=None means scalar state variable.
    """
    lines = vars_text.split("\n")

    # Locate vars == line
    vars_line_idx = next(
        (i for i, l in enumerate(lines) if re.match(r"\s*vars\s*==", l)), None
    )
    if vars_line_idx is None:
        return vars_text

    # Find last non-blank, non-comment content line before vars_line_idx
    last_var_idx = None
    for i in range(vars_line_idx - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith(r"\*") and not stripped.startswith("(*"):
            last_var_idx = i
            break

    if last_var_idx is not None:
        # Add comma after the variable identifier on that line (if missing)
        m = re.match(r"(\s+\w+)(.*)", lines[last_var_idx])
        if m:
            ident_end = m.end(1)
            rest = lines[last_var_idx][ident_end:]
            if not rest.lstrip().startswith(","):
                lines[last_var_idx] = (
                    lines[last_var_idx][:ident_end] + ","
                    + lines[last_var_idx][ident_end:]
                )
        # Insert new variable line
        if domain:
            comment = (
                f'\\* function {domain} -> {{"Fresh","InFlight","Consumed"}}'
            )
        else:
            comment = '\\* scalar lifecycle state: "Ready" | "InFlight" | "Done"'
        lines.insert(last_var_idx + 1, f"    {new_var}      {comment}")

    # Update vars == <<...>> to include new_var
    new_lines = []
    for l in lines:
        new_lines.append(
            re.sub(
                r"(vars\s*==\s*<<)([^>]+)(>>)",
                lambda mm: f"{mm.group(1)}{mm.group(2)}, {new_var}{mm.group(3)}",
                l,
            )
        )
    return "\n".join(new_lines)


def _unch_clause(vars_: list[str]) -> str:
    """Return UNCHANGED clause for a list of variable names."""
    if not vars_:
        return ""
    if len(vars_) == 1:
        return f"/\\ UNCHANGED {vars_[0]}"
    return f"/\\ UNCHANGED <<{', '.join(vars_)}>>"


def _add_constant_to_block(const_text: str, new_const: str,
                            comment: str = "") -> str:
    """Insert *new_const* into a CONSTANTS block after the last existing entry.

    Adds a trailing comma to the preceding last constant so TLA+/SANY accepts
    the comma-separated CONSTANTS list.
    """
    lines = const_text.rstrip().split("\n")
    # Find last non-blank non-comment non-CONSTANTS line (the last actual constant)
    last_idx = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if (stripped and not stripped.startswith(r"\*")
                and not stripped.startswith("CONSTANTS")):
            last_idx = i
            break
    cmt = f"   \\* {comment}" if comment else ""
    if last_idx is None:
        return const_text.rstrip() + f"\n    {new_const}{cmt}\n"
    # Add a trailing comma to the identifier on last_idx (before any comment)
    ln = lines[last_idx]
    m = re.match(r"(\s*)(\w+)(.*)", ln)
    if m:
        indent, ident, rest = m.group(1), m.group(2), m.group(3)
        # Only add comma if one isn't already there
        rest_stripped = rest.lstrip()
        if not rest_stripped.startswith(","):
            lines[last_idx] = f"{indent}{ident}," + rest
    # Insert new constant line after last_idx, BEFORE any continuation comments
    lines.insert(last_idx + 1, f"    {new_const}{cmt}")
    return "\n".join(lines) + "\n"


def _get_op_name(op_text: str) -> Optional[str]:
    """Extract the operator name from a block's text (first identifier)."""
    m = re.match(r"\s*([A-Za-z_]\w*)", op_text)
    return m.group(1) if m else None


def _append_unch_to_action(op_text: str, new_var: str) -> str:
    """Append '/\\ UNCHANGED new_var' after the last /\\ conjunct in an action."""
    lines = op_text.rstrip("\n").split("\n")
    last_conj = max(
        (i for i, ln in enumerate(lines) if ln.lstrip().startswith("/\\")),
        default=-1,
    )
    if last_conj < 0:
        return op_text
    lines.insert(last_conj + 1, f"    /\\ UNCHANGED {new_var}")
    return "\n".join(lines) + "\n"


def state_inject_with_correlation_spec(sg) -> tuple[Optional[str], Optional[str]]:
    """
    Graph mutation: inject a global monotonic clock + staleness invariant.

    Models the oracle-staleness / deadline-bypass bug class:
    - New CONSTANT: FRESHNESS  (max clock value before data is stale)
    - New var:      global_clock \in Nat
    - New action:   Tick (advance clock while clock <= FRESHNESS)
    - UNCHANGED global_clock added to all existing actions (required by TLA+)
    - New invariant: StaleDataRejected — payment must not occur when
      global_clock > FRESHNESS (violated because original actions lack
      the staleness guard)

    TLC counterexample: Init → Tick → Tick → BuggyAction → VIOLATED
    (clock=2 > FRESHNESS=1, but payment still proceeds)

    Returns (new_tla_text, new_module_name) or (None, None) if no suitable
    payment action is found.
    """
    sys.path.insert(0, str(HERE / "tools"))
    from spec_graph import parse_spec  # noqa: F401 — side-effect: registers parse_spec

    target = _detect_payment_action(sg)
    if target is None:
        return None, None

    mn = sg.module_name
    new_module = mn + "_Inject"

    is_scalar = target["scalar"]
    param = target["param"]
    domain = target["domain"]
    payment_var = target["payment_var"]
    all_orig_vars = sg.variables   # original var names; global_clock not yet in list
    clock_var = "global_clock"

    # UNCHANGED of all original variables (Tick touches only global_clock)
    tick_unch = _unch_clause(all_orig_vars)

    # Collect all action operator names (need UNCHANGED global_clock added)
    action_op_names = {
        node for node, attrs in sg.g.nodes(data=True)
        if attrs.get("kind") == "action"
    }

    new_parts: list[str] = []
    tick_inserted = False

    for blk in sg.blocks:
        text = blk.text

        if blk.kind == "header":
            text = text.replace(f"MODULE {mn}", f"MODULE {new_module}", 1)

        elif blk.kind == "constants" and blk.text.lstrip().startswith("CONSTANTS"):
            text = _add_constant_to_block(
                text, "FRESHNESS",
                "max clock steps before data is considered stale"
            )

        elif blk.kind == "variables":
            text = _add_variable_to_block(text, clock_var, None)
            # Fix the generic comment: global_clock is a Nat counter, not lifecycle
            text = text.replace(
                f'{clock_var}      \\* scalar lifecycle state: "Ready" | "InFlight" | "Done"',
                f'{clock_var}      \\* Nat: global monotonic clock (staleness proxy)',
            )

        elif blk.kind == "operator" and re.match(r"TypeInvariant\s*==", blk.text):
            lines = text.rstrip().split("\n")
            last_conj = max(
                (i for i, l in enumerate(lines) if l.strip().startswith("/\\")),
                default=len(lines) - 1,
            )
            lines.insert(last_conj + 1, f"    /\\ {clock_var} \\in Nat")
            text = "\n".join(lines) + "\n"

        elif blk.kind == "operator" and re.match(r"Init\s*==", blk.text):
            lines = text.rstrip().split("\n")
            last_conj = max(
                (i for i, l in enumerate(lines) if l.strip().startswith("/\\")),
                default=len(lines) - 1,
            )
            lines.insert(last_conj + 1, f"    /\\ {clock_var} = 0")
            text = "\n".join(lines) + "\n"

        elif blk.kind == "operator" and re.match(r"Next\s*==", blk.text):
            # Rewrite Next to add Tick as a top-level disjunct
            m = re.match(r"(Next\s*==\s*)([\s\S]+)", text.rstrip())
            if m:
                original_body = m.group(2).strip()
                text = (
                    f"Next ==\n"
                    f"    \\/ ({original_body})\n"
                    f"    \\/ Tick\n"
                    f"\n"
                )
            elif not text.rstrip().endswith("\\/ Tick"):
                text = text.rstrip() + "\n    \\/ Tick\n\n"

        elif blk.kind == "operator":
            # For action operators: append UNCHANGED global_clock
            op_name = _get_op_name(blk.text)
            if op_name in action_op_names and clock_var not in blk.text:
                text = _append_unch_to_action(text, clock_var)

        new_parts.append(text)

        # Insert Tick definition right after the buggy action block
        action_name = target["action_name"]
        if (blk.kind == "operator" and not tick_inserted and
                (blk.text.startswith(f"{action_name}(")
                 or (is_scalar and blk.text.startswith(f"{action_name} ==")))):
            tick_def = (
                f"Tick ==\n"
                f"    /\\ {clock_var} <= FRESHNESS\n"
                f"    /\\ {clock_var}' = {clock_var} + 1\n"
                f"    {tick_unch}\n"
                f"\n"
            )
            new_parts.append(tick_def)
            tick_inserted = True

    result = "".join(new_parts)

    # Build staleness invariant and inject before the footer (==== line)
    if is_scalar:
        inv_def = (
            f"StaleDataRejected ==\n"
            f"    {payment_var} > 0 => {clock_var} <= FRESHNESS\n"
            f"\n"
        )
    else:
        inv_def = (
            f"StaleDataRejected ==\n"
            f"    \\A p \\in {domain} :"
            f" {payment_var}[p] > 0 => {clock_var} <= FRESHNESS\n"
            f"\n"
        )

    footer_m = re.search(r"\n={4,}\s*\n?$", result)
    if footer_m:
        result = (result[:footer_m.start()] + "\n" + inv_def
                  + result[footer_m.start():])
    else:
        result += inv_def

    if not result.endswith("\n"):
        result += "\n"

    return result, new_module


def _extract_cfg_constants(cfg_text: str) -> str:
    """Extract the CONSTANTS block from a .cfg, stopping at the next section."""
    # Stop at INVARIANTS / PROPERTIES / SPECIFICATION / other section keywords
    m = re.search(
        r"CONSTANTS([\s\S]*?)(?=\n(?:INVARIANTS|PROPERTIES|SPECIFICATION|"
        r"INIT|NEXT|SYMMETRY|CONSTRAINT|SYMMETRY|CHECK)|\Z)",
        cfg_text,
    )
    if m:
        return "CONSTANTS" + m.group(1).rstrip()
    return "CONSTANTS"


def _make_cfg_for_inject(original_cfg_path: Path, module_name: str,
                          extra_invariants: Optional[list[str]] = None) -> str:
    """
    Build a .cfg for the state_inject spec.
    Copies original CONSTANTS, adds FRESHNESS = 1.
    """
    orig = original_cfg_path.read_text()
    constants_block = _extract_cfg_constants(orig)
    constants_block += "\n    FRESHNESS = 1"

    # Extract only the INVARIANTS section (stop at blank line or next SECTION keyword)
    inv_section_m = re.search(
        r"INVARIANTS[ \t]*\n((?:[ \t]+\w+[ \t]*\n)*)", orig
    )
    if inv_section_m:
        inv_m = re.findall(r"^\s+(\w+)\s*$", inv_section_m.group(1), re.M)
    else:
        inv_m = ["TypeInvariant"]

    base_invs = list(dict.fromkeys(inv_m + ["StaleDataRejected"]))
    if extra_invariants:
        base_invs = list(dict.fromkeys(base_invs + extra_invariants))

    inv_block = "INVARIANTS\n" + "\n".join(f"    {i}" for i in base_invs)
    return f"SPECIFICATION Spec\n\n{constants_block}\n\n{inv_block}\n"


def run_state_inject_all(spec_list: list[tuple[str, Path]],
                          dry_run: bool = False) -> list[dict]:
    """
    Apply state_inject_with_correlation to each spec in spec_list.
    TLC-discharge each result, collect novel survivors.
    """
    sys.path.insert(0, str(HERE / "tools"))
    from spec_graph import parse_spec

    MUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for spec_name, spec_dir in spec_list:
        tla_path = spec_dir / f"{spec_name}.tla"
        cfg_path = spec_dir / f"{spec_name}.cfg"
        if not tla_path.exists():
            print(f"  SKIP {spec_name}: not found", file=sys.stderr)
            continue

        sg = parse_spec(tla_path)
        new_text, new_module = state_inject_with_correlation_spec(sg)
        if new_text is None:
            print(f"  SKIP {spec_name}: no payment action detected",
                  file=sys.stderr)
            results.append({"spec": spec_name, "status": "no_target"})
            continue

        print(f"  {spec_name} → {new_module}", file=sys.stderr)

        if dry_run:
            print(new_text[:600], file=sys.stderr)
            results.append({"spec": spec_name, "status": "dry_run",
                             "module": new_module})
            continue

        cfg_text = _make_cfg_for_inject(cfg_path, new_module)

        print(f"    running TLC...", file=sys.stderr)
        tlc = run_tlc_on_text(new_text, new_module, cfg_text, timeout=90)

        if tlc["error"]:
            print(f"    TLC ERROR: {tlc['error']}", file=sys.stderr)
            print(f"    output: {tlc['output'][:500]}", file=sys.stderr)
            results.append({"spec": spec_name, "status": f"tlc-{tlc['error']}",
                             "module": new_module})
            continue

        if not tlc["violated"]:
            print(f"    invariant HOLDS — staleness not reachable",
                  file=sys.stderr)
            results.append({"spec": spec_name, "status": "holds",
                             "module": new_module})
            continue

        print(f"    VIOLATED — trace_hash={tlc['trace_hash']}",
              file=sys.stderr)

        out_tla = MUT_DIR / f"{new_module}.tla"
        out_cfg = MUT_DIR / f"{new_module}.cfg"
        out_tla.write_text(
            f"\\* MUTATION: state_inject_with_correlation({spec_name})\n"
            f"\\* parent: {spec_name}\n"
            f"\\* trace_hash: {tlc['trace_hash']}\n\n"
            + new_text
        )
        out_cfg.write_text(cfg_text)
        print(f"    → {out_tla.name}", file=sys.stderr)

        results.append({
            "spec": spec_name,
            "status": "novel",
            "module": new_module,
            "trace_hash": tlc["trace_hash"],
            "tla_path": str(out_tla),
        })

    return results


def action_subdivide_spec(sg) -> tuple[Optional[str], Optional[str]]:
    """
    Graph mutation: split a payment action into pre/reenter/post atomic steps.

    Returns (new_tla_text, new_module_name) or (None, None) if the spec
    has no suitable payment action.

    The three sub-actions expose a reentrancy window:
      A_pre   — guard Fresh→InFlight + payment write (payment before state update)
      Reenter — guard InFlight + payment write again (reentrancy bug)
      A_post  — guard InFlight→Consumed + counter write

    TLC should find a violation of the payment invariant via:
      A_pre(x) → Reenter(x) → (invariant violated)
    """
    sys.path.insert(0, str(HERE / "tools"))
    from spec_graph import parse_spec  # imported here to avoid circular at module load

    target = _detect_payment_action(sg)
    if target is None:
        return None, None

    mn = sg.module_name
    new_module = mn + "_Subdiv"

    is_scalar = target["scalar"]
    param = target["param"]
    domain = target["domain"]
    payment_var = target["payment_var"]
    payment_line = target["payment_line"]
    counter_var = target["counter_var"]
    counter_line = target["counter_line"]
    bound_guard = target["bound_guard"]
    other_vars = target["other_vars"]
    action_name = target["action_name"]
    state_var = "inflight_state"

    # Sub-action names
    pre_name = action_name + "_pre"
    reenter_name = "Reenter_" + action_name
    post_name = action_name + "_post"

    # UNCHANGED clauses (include other_vars that the original action didn't touch)
    unch_pre = _unch_clause([counter_var] + other_vars)
    unch_reenter = _unch_clause([counter_var, state_var] + other_vars)
    unch_post = _unch_clause([payment_var] + other_vars)

    # Build the new spec block by block
    new_parts: list[str] = []

    for idx, blk in enumerate(sg.blocks):
        text = blk.text

        if blk.kind == "header":
            text = text.replace(f"MODULE {mn}", f"MODULE {new_module}", 1)

        elif blk.kind == "variables":
            text = _add_variable_to_block(text, state_var, domain)

        elif blk.kind == "operator" and blk.text.startswith("TypeInvariant"):
            lines = text.rstrip().split("\n")
            last_conj = max(
                (i for i, l in enumerate(lines) if l.strip().startswith("/\\")),
                default=len(lines) - 1,
            )
            if is_scalar:
                inv_line = (
                    f'    /\\ {state_var} \\in {{"Ready", "InFlight", "Done"}}'
                )
            else:
                inv_line = (
                    f'    /\\ {state_var} \\in [{domain} -> '
                    f'{{"Fresh", "InFlight", "Consumed"}}]'
                )
            lines.insert(last_conj + 1, inv_line)
            text = "\n".join(lines) + "\n"

        elif blk.kind == "operator" and blk.text.startswith("Init"):
            lines = text.rstrip().split("\n")
            last_conj = max(
                (i for i, l in enumerate(lines) if l.strip().startswith("/\\")),
                default=len(lines) - 1,
            )
            if is_scalar:
                init_line = f'    /\\ {state_var}   = "Ready"'
            else:
                init_line = (
                    f'    /\\ {state_var}   = [{param} \\in {domain} |-> "Fresh"]'
                )
            lines.insert(last_conj + 1, init_line)
            text = "\n".join(lines) + "\n"

        elif blk.kind == "operator" and (
            blk.text.startswith(f"{action_name}(")
            or (is_scalar and blk.text.startswith(f"{action_name} =="))
        ):
            # Replace with the three sub-actions
            bound_line = f"    {bound_guard}\n" if bound_guard else ""
            if is_scalar:
                # Non-parametric scalar version
                text = (
                    f"{pre_name} ==\n"
                    f"    /\\ {state_var} = \"Ready\"\n"
                    f"{bound_line}"
                    f"    /\\ {state_var}' = \"InFlight\"\n"
                    f"    {payment_line}\n"
                    f"    {unch_pre}\n"
                    f"\n"
                    f"{reenter_name} ==\n"
                    f"    /\\ {state_var} = \"InFlight\"\n"
                    f"{bound_line}"
                    f"    {payment_line}\n"
                    f"    {unch_reenter}\n"
                    f"\n"
                    f"{post_name} ==\n"
                    f"    /\\ {state_var} = \"InFlight\"\n"
                    f"    /\\ {state_var}' = \"Done\"\n"
                    f"    {counter_line}\n"
                    f"    {unch_post}\n"
                    f"\n"
                )
            else:
                # Parametric function version
                text = (
                    f"{pre_name}({param}) ==\n"
                    f"    /\\ {param} \\in {domain}\n"
                    f"    /\\ {state_var}[{param}] = \"Fresh\"\n"
                    f"{bound_line}"
                    f"    /\\ {state_var}' = [{state_var} EXCEPT ![{param}] = \"InFlight\"]\n"
                    f"    {payment_line}\n"
                    f"    {unch_pre}\n"
                    f"\n"
                    f"{reenter_name}({param}) ==\n"
                    f"    /\\ {param} \\in {domain}\n"
                    f"    /\\ {state_var}[{param}] = \"InFlight\"\n"
                    f"{bound_line}"
                    f"    {payment_line}\n"
                    f"    {unch_reenter}\n"
                    f"\n"
                    f"{post_name}({param}) ==\n"
                    f"    /\\ {param} \\in {domain}\n"
                    f"    /\\ {state_var}[{param}] = \"InFlight\"\n"
                    f"    /\\ {state_var}' = [{state_var} EXCEPT ![{param}] = \"Consumed\"]\n"
                    f"    {counter_line}\n"
                    f"    {unch_post}\n"
                    f"\n"
                )

        elif blk.kind == "operator" and blk.text.startswith("Next"):
            if is_scalar:
                text = (
                    f"Next ==\n"
                    f"    \\/ {pre_name}\n"
                    f"    \\/ {reenter_name}\n"
                    f"    \\/ {post_name}\n"
                    f"\n"
                )
            else:
                text = (
                    f"Next ==\n"
                    f"    \\E {param} \\in {domain} :\n"
                    f"        \\/ {pre_name}({param})\n"
                    f"        \\/ {reenter_name}({param})\n"
                    f"        \\/ {post_name}({param})\n"
                    f"\n"
                )

        elif blk.kind == "operator" and blk.text.startswith("Fairness"):
            if is_scalar:
                text = (
                    f"Fairness ==\n"
                    f"    WF_vars({pre_name} \\/ {reenter_name} \\/ {post_name})\n"
                    f"\n"
                )
            else:
                text = (
                    f"Fairness ==\n"
                    f"    \\A {param} \\in {domain} :\n"
                    f"        WF_vars({pre_name}({param}) \\/ {reenter_name}({param})"
                    f" \\/ {post_name}({param}))\n"
                    f"\n"
                )

        new_parts.append(text)

    result = "".join(new_parts)
    if not result.endswith("\n"):
        result += "\n"
    return result, new_module


def run_tlc_on_text(tla_text: str, module_name: str,
                    cfg_text: str, timeout: int = 60) -> dict:
    """
    Write tla_text + cfg_text to a temp dir, run TLC, return result dict:
    {violated: bool, error: str|None, trace_hash: str, output: str}
    """
    import hashlib, subprocess
    tmp = tempfile.mkdtemp(prefix="shape_subdiv_")
    try:
        tla_path = os.path.join(tmp, module_name + ".tla")
        cfg_path = os.path.join(tmp, module_name + ".cfg")
        jar_link = os.path.join(tmp, "tla2tools.jar")
        with open(tla_path, "w") as f:
            f.write(tla_text)
        with open(cfg_path, "w") as f:
            f.write(cfg_text)
        if not os.path.exists(jar_link):
            os.symlink(TLA_JAR, jar_link)

        cmd = [
            "java", "-XX:+UseParallelGC",
            "-cp", jar_link,
            "tlc2.TLC",
            "-config", cfg_path,
            "-deadlock",
            tla_path,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        out = proc.stdout + proc.stderr
        violated = "is violated" in out or "Invariant" in out and "violated" in out
        error = None
        if proc.returncode != 0 and not violated:
            # Check for parse/type errors
            if "Error:" in out and "violated" not in out:
                error = "tlc-error"
        trace_hash = hashlib.md5(out.encode()).hexdigest()[:12]
        return {
            "violated": violated,
            "error": error,
            "trace_hash": trace_hash,
            "output": out[:2000],
        }
    except subprocess.TimeoutExpired:
        return {"violated": False, "error": "timeout", "trace_hash": "", "output": ""}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _make_cfg_for_subdiv(original_cfg_path: Path, module_name: str,
                          extra_invariants: Optional[list[str]] = None) -> str:
    """
    Build a .cfg for the subdivided spec by copying the original cfg's
    CONSTANTS block and updating SPECIFICATION + INVARIANTS.
    """
    orig = original_cfg_path.read_text()
    # Extract CONSTANTS block
    const_m = re.search(r"(CONSTANTS\s*\n(?:.*\n)*?)(?=\n\w|\Z)", orig, re.M)
    constants_block = const_m.group(1).rstrip() if const_m else ""

    # Extract INVARIANTS from original
    inv_m = re.findall(r"^\s*(\w+)\s*$", re.search(
        r"INVARIANTS\s*\n((?:\s*\w+\s*\n)*)", orig, re.M
    ).group(1) if re.search(r"INVARIANTS\s*\n", orig, re.M) else "",
    re.M)
    if not inv_m:
        inv_m = ["TypeInvariant"]

    if extra_invariants:
        inv_m = list(dict.fromkeys(inv_m + extra_invariants))

    inv_block = "INVARIANTS\n" + "\n".join(f"    {i}" for i in inv_m)

    cfg = f"SPECIFICATION Spec\n\n{constants_block}\n\n{inv_block}\n"
    return cfg


def run_action_subdivide_all(spec_list: list[tuple[str, Path]],
                              dry_run: bool = False) -> list[dict]:
    """
    Apply action_subdivide to each spec in spec_list.
    TLC-discharge each result, collect novel survivors.
    """
    sys.path.insert(0, str(HERE / "tools"))
    from spec_graph import parse_spec

    MUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for spec_name, spec_dir in spec_list:
        tla_path = spec_dir / f"{spec_name}.tla"
        cfg_path = spec_dir / f"{spec_name}.cfg"
        if not tla_path.exists():
            print(f"  SKIP {spec_name}: not found", file=sys.stderr)
            continue

        sg = parse_spec(tla_path)
        new_text, new_module = action_subdivide_spec(sg)
        if new_text is None:
            print(f"  SKIP {spec_name}: no payment action detected",
                  file=sys.stderr)
            results.append({"spec": spec_name, "status": "no_target"})
            continue

        print(f"  {spec_name} → {new_module}", file=sys.stderr)

        if dry_run:
            print(new_text[:400], file=sys.stderr)
            results.append({"spec": spec_name, "status": "dry_run",
                             "module": new_module})
            continue

        # Build cfg
        cfg_text = _make_cfg_for_subdiv(cfg_path, new_module)

        # TLC-discharge
        print(f"    running TLC...", file=sys.stderr)
        tlc = run_tlc_on_text(new_text, new_module, cfg_text, timeout=90)

        if tlc["error"]:
            print(f"    TLC ERROR: {tlc['error']}", file=sys.stderr)
            print(f"    output: {tlc['output'][:500]}", file=sys.stderr)
            results.append({"spec": spec_name, "status": f"tlc-{tlc['error']}",
                             "module": new_module})
            continue

        if not tlc["violated"]:
            print(f"    invariant HOLDS — not a reentrancy split",
                  file=sys.stderr)
            results.append({"spec": spec_name, "status": "holds",
                             "module": new_module})
            continue

        print(f"    VIOLATED — trace_hash={tlc['trace_hash']}",
              file=sys.stderr)

        # Write to mutations dir
        out_tla = MUT_DIR / f"{new_module}.tla"
        out_cfg = MUT_DIR / f"{new_module}.cfg"
        out_tla.write_text(
            f"\\* MUTATION: action_subdivide({spec_name})\n"
            f"\\* parent: {spec_name}\n"
            f"\\* trace_hash: {tlc['trace_hash']}\n\n"
            + new_text
        )
        out_cfg.write_text(cfg_text)
        print(f"    → {out_tla.name}", file=sys.stderr)

        results.append({
            "spec": spec_name,
            "status": "novel",
            "module": new_module,
            "trace_hash": tlc["trace_hash"],
            "tla_path": str(out_tla),
        })

    return results


def _generate_mutations_inline(runs: int):
    """Generate mutations using spec_mutator's operators but bypass its
    lark grammar validator (which rejects add_state_var output). TLC
    discharge is the only fitness gate."""
    sys.path.insert(0, str(HERE / "tools"))
    import spec_mutator as sm
    import random, hashlib, shutil, tempfile
    rng = random.Random(42)
    MUT_DIR.mkdir(parents=True, exist_ok=True)
    # Run baseline TLC for each spec
    originals = {}
    for spec, d in sm.SPEC_LIST:
        r = sm.run_tlc(os.path.join(d, spec + ".tla"),
                       os.path.join(d, spec + ".cfg"))
        originals[spec] = r["trace_hash"]
        print(f"  [baseline] {spec}: hash={r['trace_hash']}", file=sys.stderr)
    tmp_root = tempfile.mkdtemp(prefix="shape_evolve_")
    novel_count = 0
    try:
        for spec, d in sm.SPEC_LIST:
            src = open(os.path.join(d, spec + ".tla")).read()
            cfg_src = open(os.path.join(d, spec + ".cfg")).read()
            for run in range(runs):
                # Prefer semantic mutators for embedding-shift discovery
                fn = rng.choices(sm.MUTATIONS,
                                 weights=[1, 1, 1, 1, 5, 3],  # heavy on semantic
                                 k=1)[0]
                result = fn(src, rng)
                if result is None:
                    print(f"  [{spec} #{run}] {fn.__name__}: no-target", file=sys.stderr)
                    continue
                new_src, kind = result
                wd = os.path.join(tmp_root, f"{spec}_{run}")
                os.makedirs(wd, exist_ok=True)
                tla_t = os.path.join(wd, spec + ".tla")
                cfg_t = os.path.join(wd, spec + ".cfg")
                jl = os.path.join(wd, "tla2tools.jar")
                if not os.path.exists(jl):
                    os.symlink(sm.TLA_JAR, jl)
                open(tla_t, "w").write(new_src)
                open(cfg_t, "w").write(cfg_src)
                r = sm.run_tlc(tla_t, cfg_t, timeout=30)
                if r["error"]:
                    print(f"  [{spec} #{run}] {kind}: tlc-{r['error']}", file=sys.stderr)
                    continue
                if not r["violated"]:
                    print(f"  [{spec} #{run}] {kind}: invariant holds (fixed)", file=sys.stderr)
                    continue
                if r["trace_hash"] == originals[spec]:
                    print(f"  [{spec} #{run}] {kind}: equivalent", file=sys.stderr)
                    continue
                # Novel!
                out = MUT_DIR / f"{spec}_mut_{run}.tla"
                out.write_text(
                    f"\\* MUTATION: {kind}\n"
                    f"\\* original hash: {originals[spec]}\n"
                    f"\\* new hash: {r['trace_hash']}\n\n{new_src}")
                novel_count += 1
                print(f"  [{spec} #{run}] {kind}: NOVEL → {out.name}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print(f"\nnovel mutations: {novel_count}", file=sys.stderr)


def load_unmatched_findings() -> list[dict]:
    """Findings from sherlock_coverage.jsonl with no existing shape at cos>0.7."""
    if not SHERLOCK_COVERAGE.exists():
        sys.exit(f"missing: {SHERLOCK_COVERAGE}. Run "
                 "tools/calibrate_against_sherlock.py first.")
    out = []
    for line in SHERLOCK_COVERAGE.read_text().splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        for f in rec.get("findings", []):
            if f.get("top1_cos", 0) <= COS_COVER:
                out.append({"id": f["id"], "severity": f["severity"],
                            "title": f["title"], "contest": rec["slug"]})
    return out


def extract_signature(tla_path: Path) -> str:
    """Build a shape signature from a .tla module: doc header + invariant +
    state vars + action names. This is what we embed."""
    text = tla_path.read_text(errors="replace")
    # Header comment block (between ( * and * ))
    m = re.search(r"\(\*(.*?)\*\)", text, re.S)
    header = m.group(1) if m else ""
    # All invariant declarations of the form `Name == ...` whose LHS doesn't
    # start with internal keywords
    invs = []
    for m in re.finditer(r"^([A-Z]\w+)\s*==\s*(.+?)(?=\n[A-Z][\w]*\s*==|\n=====|\Z)",
                         text, re.M | re.S):
        name = m.group(1)
        if name in ("Init", "Next", "Spec", "TypeInvariant", "Fairness"):
            continue
        invs.append(f"{name}: {m.group(2).strip()[:200]}")
    # VARIABLES list
    vm = re.search(r"VARIABLES\s*\n((?:\s+\w+,?\s*\n)+)", text)
    varlist = ""
    if vm:
        varlist = " ".join(x.strip().rstrip(",") for x in vm.group(1).split("\n")
                           if x.strip())
    # Mutation kind if present — weight it 3× to dominate over the parent's
    # header (which would otherwise pin the embedding to the parent shape).
    mut = ""
    mm = re.search(r"\\\* MUTATION:\s*(.+)", text)
    if mm:
        mut_kind = mm.group(1).strip()
        # Translate add_state_var(staleness_window) → "bug class: staleness
        # window check; precision; freshness; timeout" — semantic hints
        # that match Sherlock unmatched-finding vocabulary.
        sem_hints = ""
        if mut_kind.startswith("add_state_var(staleness"):
            sem_hints = "bug class: oracle staleness; stale price; missing freshness check; timeout window"
        elif mut_kind.startswith("add_state_var(decimals"):
            sem_hints = "bug class: decimals mismatch; precision loss; scaling error; integration assumption"
        elif mut_kind.startswith("add_state_var(chain_id"):
            sem_hints = "bug class: cross-chain replay; missing chain id binding; multi-chain replay"
        elif mut_kind.startswith("add_state_var(token_addr"):
            sem_hints = "bug class: hardcoded address; mainnet WETH constant; chain-specific deployment"
        elif mut_kind.startswith("add_state_var(paused"):
            sem_hints = "bug class: pause bypass; missing whenNotPaused; circuit breaker missing"
        elif mut_kind.startswith("add_state_var(rebase"):
            sem_hints = "bug class: rebasing token assumption; OETH stETH balance drift; share-asset desync"
        elif mut_kind.startswith("add_state_var(liquidation"):
            sem_hints = "bug class: liquidation frontrun; price manipulation pre-liquidation; bad debt"
        elif mut_kind.startswith("add_state_var(vesting"):
            sem_hints = "bug class: vesting accrual after exit; reward double-accrue; emission drift"
        elif mut_kind.startswith("add_state_var(oracle_price"):
            sem_hints = "bug class: oracle price manipulation; TWAP attack; spot-feed assumption"
        elif mut_kind.startswith("add_guard"):
            sem_hints = "bug class: access control bypass; missing modifier; role check absent"
        elif mut_kind.startswith("state_inject_with_correlation"):
            sem_hints = (
                "bug class: oracle staleness; stale data acceptance; "
                "missing freshness check; deadline bypass; expired data; "
                "global clock; timestamp; time-based invalidation; "
                "stale price feed; freshness window; heartbeat timeout"
            )
        elif mut_kind.startswith("action_subdivide"):
            sem_hints = (
                "bug class: reentrancy; CEI violation; external call before update; "
                "reentrant withdrawal; check-effects-interactions pattern; "
                "callback exploitation; cross-function reentrancy"
            )
        mut = f"mutation: {mut_kind} | {mut_kind} | {mut_kind}\n{sem_hints}"
    sig = f"{mut}\nvars: {varlist}\nheader: {header[:1500]}\ninvariants: {' | '.join(invs[:5])[:1500]}"
    return sig


def load_existing_shape_signatures() -> dict[str, str]:
    """For anti-similarity penalty: signatures of the 9 originals."""
    out = {}
    for tla in sorted(TLA_DIR.glob("*.tla")):
        if tla.name.startswith("imported_"): continue
        out[tla.stem] = extract_signature(tla)
    return out


def score_mutations(mutations: dict[str, str],
                    unmatched: list[dict],
                    existing_sigs: dict[str, str]) -> list[dict]:
    """Embed each mutation signature + each unmatched finding title,
    measure how many unmatched findings come within cos>0.7. Apply
    anti-similarity penalty."""
    sys.path.insert(0, str(HERE / "tools"))
    import spec_retrieval as sr
    from fastembed import TextEmbedding
    import numpy as np

    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # Embed unmatched findings
    finding_texts = [sr._lift_idents(f["title"]) for f in unmatched]
    finding_embs = np.array(list(embedder.embed(finding_texts)))
    finding_norms = np.linalg.norm(finding_embs, axis=1)

    # Embed existing shape signatures (for anti-similarity)
    existing_sig_texts = [sr._lift_idents(s) for s in existing_sigs.values()]
    existing_embs = np.array(list(embedder.embed(existing_sig_texts)))
    existing_norms = np.linalg.norm(existing_embs, axis=1)
    existing_names = list(existing_sigs.keys())

    # Embed mutation signatures
    mut_names = list(mutations.keys())
    mut_texts = [sr._lift_idents(s) for s in mutations.values()]
    mut_embs = np.array(list(embedder.embed(mut_texts)))
    mut_norms = np.linalg.norm(mut_embs, axis=1)

    results = []
    for i, name in enumerate(mut_names):
        sims_findings = finding_embs @ mut_embs[i] / (finding_norms * mut_norms[i])
        covered = sum(1 for s in sims_findings if s > COS_COVER)
        covered_findings = [unmatched[j]["title"][:50]
                            for j in range(len(unmatched))
                            if sims_findings[j] > COS_COVER]
        # Anti-similarity: closest existing shape
        sims_existing = existing_embs @ mut_embs[i] / (existing_norms * mut_norms[i])
        closest_idx = int(sims_existing.argmax())
        closest_cos = float(sims_existing[closest_idx])
        penalty = closest_cos > COS_ANTI
        fitness = 0 if penalty else covered
        results.append({
            "mutation": name,
            "covered_count": covered,
            "fitness_score": fitness,
            "closest_existing": existing_names[closest_idx],
            "closest_existing_cos": closest_cos,
            "anti_sim_penalty": penalty,
            "covered_findings_sample": covered_findings[:5],
        })
    results.sort(key=lambda r: (-r["fitness_score"], -r["covered_count"]))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-only", action="store_true",
                    help="Score existing docs/tla/mutations/ without "
                         "regenerating.")
    ap.add_argument("--runs", type=int, default=0,
                    help="If >0, run spec_mutator with this many runs first.")
    ap.add_argument("--action-subdivide", action="store_true",
                    help="Apply action_subdivide graph mutation to all 9 specs, "
                         "TLC-discharge results, and report novel survivors.")
    ap.add_argument("--state-inject", action="store_true",
                    help="Apply state_inject_with_correlation to all 9 specs, "
                         "TLC-discharge results, and report novel survivors.")
    ap.add_argument("--dry-run", action="store_true",
                    help="With --action-subdivide/--state-inject: print generated "
                         "specs without running TLC.")
    args = ap.parse_args()

    if args.state_inject:
        sys.path.insert(0, str(HERE / "tools"))
        from spec_graph import SPEC_LIST
        print("state_inject_with_correlation: applying to all specs...",
              file=sys.stderr)
        inject_results = run_state_inject_all(SPEC_LIST, dry_run=args.dry_run)

        novel = [r for r in inject_results if r.get("status") == "novel"]
        print(f"\n{'=' * 60}")
        print(f"state_inject results: {len(novel)} novel survivors "
              f"out of {len(inject_results)} specs")
        for r in inject_results:
            status = r.get("status", "?")
            print(f"  {r['spec']:<40}  {status}")

        if novel and not args.dry_run:
            print("\nscoring novel survivors...", file=sys.stderr)
            try:
                unmatched = load_unmatched_findings()
                existing = load_existing_shape_signatures()
                mut_sigs = {
                    Path(r["tla_path"]).stem: extract_signature(Path(r["tla_path"]))
                    for r in novel
                }
                ranked = score_mutations(mut_sigs, unmatched, existing)
                out = HERE / "corpus" / "calibration" / "shape_evolve_ranking.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(ranked, indent=2))
                print(f"\nranking → {out}")
                for r in ranked:
                    anti = "  ←ANTI" if r["anti_sim_penalty"] else ""
                    print(f"  {r['mutation']:<50} cov={r['covered_count']:>3} "
                          f"fit={r['fitness_score']:>3} "
                          f"cos={r['closest_existing_cos']:.2f}{anti}")
            except Exception as e:
                print(f"scoring failed (missing deps?): {e}", file=sys.stderr)
        return

    if args.action_subdivide:
        sys.path.insert(0, str(HERE / "tools"))
        from spec_graph import SPEC_LIST
        print("action_subdivide: applying to all specs...", file=sys.stderr)
        subdiv_results = run_action_subdivide_all(SPEC_LIST, dry_run=args.dry_run)

        novel = [r for r in subdiv_results if r.get("status") == "novel"]
        print(f"\n{'=' * 60}")
        print(f"action_subdivide results: {len(novel)} novel survivors "
              f"out of {len(subdiv_results)} specs")
        for r in subdiv_results:
            status = r.get("status", "?")
            print(f"  {r['spec']:<40}  {status}")

        if novel and not args.dry_run:
            # Score the novel survivors
            print("\nscoring novel survivors...", file=sys.stderr)
            try:
                unmatched = load_unmatched_findings()
                existing = load_existing_shape_signatures()
                mut_sigs = {
                    Path(r["tla_path"]).stem: extract_signature(Path(r["tla_path"]))
                    for r in novel
                }
                ranked = score_mutations(mut_sigs, unmatched, existing)
                out = HERE / "corpus" / "calibration" / "shape_evolve_ranking.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(ranked, indent=2))
                print(f"\nranking → {out}")
                for r in ranked:
                    anti = "  ←ANTI" if r["anti_sim_penalty"] else ""
                    print(f"  {r['mutation']:<50} cov={r['covered_count']:>3} "
                          f"fit={r['fitness_score']:>3} "
                          f"cos={r['closest_existing_cos']:.2f}{anti}")
            except Exception as e:
                print(f"scoring failed (missing deps?): {e}", file=sys.stderr)
        return

    if args.runs > 0:
        # Inline mutation generator that bypasses spec_mutator's lark
        # validator (too strict for add_state_var output) and uses TLC
        # discharge as the only fitness gate.
        print(f"generating {args.runs} mutations per shape (TLC-only fitness)...",
              file=sys.stderr)
        _generate_mutations_inline(args.runs)

    print("loading unmatched Sherlock findings...", file=sys.stderr)
    unmatched = load_unmatched_findings()
    print(f"  {len(unmatched)} findings with no existing-shape RAG prior cos>{COS_COVER}",
          file=sys.stderr)

    print("loading mutations...", file=sys.stderr)
    mut_files = sorted(MUT_DIR.glob("*.tla"))
    mutations = {p.stem: extract_signature(p) for p in mut_files}
    print(f"  {len(mutations)} mutations: {sorted(mutations.keys())}",
          file=sys.stderr)

    if not mutations:
        sys.exit("no mutations to score. Run with --runs N to generate.")

    print("loading existing shape signatures...", file=sys.stderr)
    existing = load_existing_shape_signatures()
    print(f"  {len(existing)} existing shapes: {sorted(existing.keys())}",
          file=sys.stderr)

    print("\nscoring mutations vs unmatched findings...", file=sys.stderr)
    results = score_mutations(mutations, unmatched, existing)

    print("\n" + "=" * 70)
    print("SHAPE EVOLVE RANKING")
    print("=" * 70)
    print(f"{'mutation':<40} {'cov':>4} {'fit':>4} {'closest':<25} {'cos':>5}")
    print("-" * 80)
    for r in results:
        print(f"{r['mutation']:<40} {r['covered_count']:>4} "
              f"{r['fitness_score']:>4} {r['closest_existing']:<25} "
              f"{r['closest_existing_cos']:>5.2f}"
              + ("  ←ANTI" if r['anti_sim_penalty'] else ""))

    top = results[0] if results else None
    if top and top["fitness_score"] > 0:
        print(f"\nTOP: {top['mutation']}  fitness={top['fitness_score']}")
        print(f"  covered findings (sample):")
        for f in top["covered_findings_sample"]:
            print(f"    - {f}")
        out = HERE / "corpus" / "calibration" / "shape_evolve_ranking.json"
        out.write_text(json.dumps(results, indent=2))
        print(f"\nfull ranking → {out}")
    else:
        print("\nNo mutation passed anti-similarity penalty AND covered >0 findings.")
        print("Try: --runs 20 to generate more mutations.")


if __name__ == "__main__":
    main()
