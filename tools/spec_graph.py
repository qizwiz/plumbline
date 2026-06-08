"""
spec_graph — TLA+ spec ↔ NetworkX MultiDiGraph for graph-level shape mutations.

Nodes:
  kind=var:        a declared VARIABLE
  kind=action:     an operator whose body contains primed variables (v')
  kind=predicate:  a helper operator (no primed vars, not invariant/spec_meta)
  kind=invariant:  an operator that expresses a safety/temporal property
  kind=spec_meta:  Spec, Fairness, Next, vars, Init (structural backbone)

Edges:
  kind=reads:          action/predicate → var (unprimed reference in body)
  kind=writes:         action → var (v' reference in body)
  kind=next_disjunct:  Next → action (each disjunct in the Next formula)
  kind=init_assigns:   Init → var (each variable initialized in Init)
  kind=conjuncts:      action → predicate (predicate name appears in action body)

Round-trip guarantee:
  parse_spec(path) builds the graph but also stores the original text structure.
  serialize_spec(g, out_path) reconstructs TLA+ from the stored structure.
  round_trip_test(path) asserts serialize(parse(path)) == original text.

Usage:
  python tools/spec_graph.py --test         # round-trip all 9 shapes
  python tools/spec_graph.py --show <spec>  # print graph summary
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import networkx as nx

HERE = Path(__file__).resolve().parent.parent
TLA_DIR = HERE / "docs" / "tla"
IMPORTED_DIR = TLA_DIR / "imported"

SPEC_LIST = [
    ("Create2NonIdempotent",       TLA_DIR),
    ("CrossWalletSigReplay",       TLA_DIR),
    ("ERC4337StaticSigDoS",        TLA_DIR),
    ("FlagBypassesValidationChain", TLA_DIR),
    ("IncentiveBonusBreaksInvariant", TLA_DIR),
    ("PartialSignatureReplay",     TLA_DIR),
    ("ReentrancyDrain",            TLA_DIR),
    ("SignatureReplay",            TLA_DIR),
    ("Uint64FeeOverflow",          TLA_DIR),
]

# Operators whose names indicate spec-meta role (structural backbone).
SPEC_META_NAMES = {"Spec", "Fairness", "Next", "Init", "vars", "TypeInvariant"}

# Operator names that are always invariants (end-of-spec properties).
# We also detect invariants by convention: defined after the ==== separator
# comment block at the bottom of the spec.
INVARIANT_SIGNALS = frozenset([
    "NoOverpayment", "PaidAtMostOnce", "MonotonicPayouts",
    "SubmittedEventuallyPaid", "TrackedMatchesActual", "TrackedAtMostActual",
    "ActualMonotonic", "TrackedMonotonic",
    "ClaimedAtMostOnce", "PaidAtMostTicketPrice",
    "Authorized4337CallsExecute", "SubmittedCallTerminates", "NoBothOutcomes",
    "MonotonicOutcomes",
    "EnforcementHonored",
    "VictimTokensSafe", "AttackerCannotStealTokens",
    "NoDoubleDeploy", "SaltUsedAtMostOnce",
])


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpecBlock:
    """Raw text block parsed from the TLA+ file."""
    kind: str          # "header" | "extends" | "constants" | "assume" |
                       # "variables" | "separator" | "operator" | "footer"
    text: str          # complete verbatim text, including trailing newline


@dataclass
class SpecGraph:
    """The parsed spec as both a NetworkX graph AND a list of raw blocks
    (for round-trip serialization)."""
    module_name: str
    blocks: list[SpecBlock]                  # ordered list for round-trip
    g: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    # Map operator_name → index in blocks (for fast mutation access)
    op_block_idx: dict[str, int] = field(default_factory=dict)
    # Ordered list of variable names
    variables: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _split_blocks(text: str) -> list[SpecBlock]:
    """
    Split a TLA+ source text into raw blocks preserving all content.

    Blocks detected (in order):
      header    — the first ----- MODULE ... ----- line + docstring
      extends   — EXTENDS line(s)
      constants — CONSTANTS block
      assume    — ASSUME statement(s)
      variables — VARIABLES block (through vars ==)
      separator — a comment-separator banner (---- or ====)
      operator  — a top-level operator definition (name == ...)
      footer    — the final ===== line
    """
    lines = text.split("\n")
    # Ensure trailing newline consistency
    if lines and lines[-1] == "":
        lines = lines[:-1]

    blocks: list[SpecBlock] = []
    i = 0
    n = len(lines)

    def flush(kind: str, collected: list[str]) -> None:
        if collected:
            blocks.append(SpecBlock(kind=kind, text="\n".join(collected) + "\n"))

    # Regex for top-level operator definition start:
    # Captures: optional_leading_dashes or blank line, then Name == or Name(params) ==
    OP_START = re.compile(r"^([A-Za-z_]\w*)\s*(\([^)]*\))?\s*==(?!=)")

    collected: list[str] = []
    current_kind: str = "header"
    in_block_comment = False
    found_module = False

    # Phase 1: header (MODULE declaration)
    while i < n:
        line = lines[i]
        if re.match(r"^-{4,}\s*MODULE\s+\w+\s*-{4,}", line):
            collected.append(line)
            i += 1
            found_module = True
            break
        collected.append(line)
        i += 1

    # Collect block comment that immediately follows MODULE line (the (*...*) docstring)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("(*"):
            in_block_comment = True
        if in_block_comment:
            collected.append(line)
            i += 1
            if "*)" in line:
                in_block_comment = False
                # Continue collecting blank lines and comments that are part of header
                while i < n and lines[i].strip() == "":
                    collected.append(lines[i])
                    i += 1
            continue
        break

    flush("header", collected)
    collected = []

    # Phase 2: parse remaining blocks
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Track block comments across all phases
        if stripped.startswith("(*"):
            in_block_comment = True
        if in_block_comment:
            collected.append(line)
            i += 1
            if "*)" in stripped:
                in_block_comment = False
            continue

        # Footer line (====)
        if re.match(r"^={4,}\s*$", stripped):
            # Flush any pending block
            if collected:
                flush(current_kind, collected)
                collected = []
            # Include everything remaining as footer
            footer_lines = lines[i:]
            blocks.append(SpecBlock(kind="footer", text="\n".join(footer_lines) + "\n"))
            i = n
            continue

        # Separator line (----)
        if re.match(r"^-{4,}", stripped) and not re.match(r"^-{4,}\s*MODULE", stripped):
            if collected:
                flush(current_kind, collected)
                collected = []
            # Collect the separator + its immediate block comment if any
            sep_lines = [line]
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if nxt.startswith("(*"):
                    sep_lines.append(lines[i])
                    i += 1
                    in_bc = True
                    while i < n and in_bc:
                        sep_lines.append(lines[i])
                        if "*)" in lines[i]:
                            in_bc = False
                        i += 1
                elif nxt == "":
                    sep_lines.append(lines[i])
                    i += 1
                else:
                    break
            blocks.append(SpecBlock(kind="separator",
                                    text="\n".join(sep_lines) + "\n"))
            current_kind = "operator"  # after separator, expect operators
            continue

        # EXTENDS
        if stripped.startswith("EXTENDS") and not collected:
            flush(current_kind, collected)
            collected = []
            ext_lines = [line]
            i += 1
            # EXTENDS can span multiple lines (rare in our corpus but handle it)
            while i < n and lines[i].strip() and not re.match(
                    r"^[A-Z]", lines[i].strip()):
                ext_lines.append(lines[i])
                i += 1
            blocks.append(SpecBlock(kind="extends",
                                    text="\n".join(ext_lines) + "\n"))
            current_kind = "constants"
            continue

        # CONSTANTS
        if stripped.startswith("CONSTANTS") and current_kind in ("constants",
                                                                   "extends",
                                                                   "header"):
            flush(current_kind, collected)
            collected = []
            const_lines = [line]
            i += 1
            # Collect indented lines + block comments
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if ns.startswith("(*"):
                    const_lines.append(nxt)
                    i += 1
                    in_bc = True
                    while i < n and in_bc:
                        const_lines.append(lines[i])
                        if "*)" in lines[i]:
                            in_bc = False
                        i += 1
                    continue
                if ns.startswith("\\*") or ns == "" or nxt.startswith("    ") or nxt.startswith("\t"):
                    const_lines.append(nxt)
                    i += 1
                else:
                    break
            blocks.append(SpecBlock(kind="constants",
                                    text="\n".join(const_lines) + "\n"))
            current_kind = "assume"
            continue

        # ASSUME
        if stripped.startswith("ASSUME") and current_kind in ("assume",
                                                               "constants"):
            flush(current_kind, collected)
            collected = []
            # Collect all consecutive ASSUME lines
            assume_lines = []
            while i < n:
                nxt = lines[i].strip()
                if nxt.startswith("ASSUME") or (assume_lines and
                        (lines[i].startswith("    ") or nxt == ""
                         or nxt.startswith("\\*"))):
                    assume_lines.append(lines[i])
                    i += 1
                else:
                    break
            blocks.append(SpecBlock(kind="assume",
                                    text="\n".join(assume_lines) + "\n"))
            current_kind = "variables"
            continue

        # VARIABLES block (can appear after operators in some specs)
        if stripped.startswith("VARIABLES"):
            flush(current_kind, collected)
            collected = []
            var_lines = [line]
            i += 1
            # Collect variable declarations (indented) + comments
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if (nxt.startswith("    ") or nxt.startswith("\t")
                        or ns.startswith("\\*") or ns == ""):
                    var_lines.append(nxt)
                    i += 1
                elif ns.startswith("(*"):
                    var_lines.append(nxt)
                    i += 1
                    in_bc = True
                    while i < n and in_bc:
                        var_lines.append(lines[i])
                        if "*)" in lines[i]:
                            in_bc = False
                        i += 1
                else:
                    break
            # Now collect vars == ... line
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if re.match(r"^vars\s*==", ns):
                    var_lines.append(nxt)
                    i += 1
                    # Also grab the rest of vars == if it spans lines
                    while i < n and (lines[i].startswith("    ") or
                                      lines[i].strip() == ""):
                        var_lines.append(lines[i])
                        i += 1
                    break
                elif ns == "" or ns.startswith("\\*"):
                    var_lines.append(nxt)
                    i += 1
                else:
                    break
            blocks.append(SpecBlock(kind="variables",
                                    text="\n".join(var_lines) + "\n"))
            current_kind = "operator"
            continue

        # Top-level operator definition
        op_m = OP_START.match(line)
        if op_m:
            flush(current_kind, collected)
            collected = []
            current_kind = "operator"
            op_lines = [line]
            i += 1
            # Collect the operator body: indented lines, blank lines, block
            # comments, and lines starting with (* (even unindented) until
            # the next top-level definition.
            in_bc = False
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                # Block comment?
                if ns.startswith("(*"):
                    in_bc = True
                if in_bc:
                    op_lines.append(nxt)
                    i += 1
                    if "*)" in nxt:
                        in_bc = False
                    continue
                # End of this operator: next unindented non-comment line
                # that starts a new definition, EXTENDS, or separator
                if ns == "" or nxt.startswith("    ") or nxt.startswith("\t") or ns.startswith("\\*"):
                    op_lines.append(nxt)
                    i += 1
                    continue
                # Peek: is this another top-level operator or keyword?
                if (OP_START.match(nxt) or ns.startswith("VARIABLES")
                        or ns.startswith("ASSUME") or ns.startswith("EXTENDS")
                        or re.match(r"^-{4,}", ns) or re.match(r"^={4,}", ns)):
                    break
                # Otherwise it's a continuation (e.g., multi-line body)
                op_lines.append(nxt)
                i += 1
            flush("operator", op_lines)
            continue

        # Fallback: collect into current_kind
        collected.append(line)
        i += 1

    if collected:
        flush(current_kind, collected)

    return blocks


def _extract_variables(blocks: list[SpecBlock]) -> list[str]:
    """Extract ordered variable names from the VARIABLES block."""
    for blk in blocks:
        if blk.kind == "variables":
            # Strip comments and find all identifiers in the VARIABLES section
            # (exclude the vars == ... line)
            var_text = re.sub(r"\\\*[^\n]*", "", blk.text)   # line comments
            var_text = re.sub(r"\(\*.*?\*\)", "", var_text, flags=re.S)  # block comments
            # Find the VARIABLES keyword, then grab identifiers until vars ==
            m = re.search(r"VARIABLES\s*(.*?)(?:\bvars\s*==|\Z)", var_text, re.S)
            if m:
                body = m.group(1)
                names = re.findall(r"\b([a-z_]\w*)\b", body)
                # Filter out TLA+ keywords and common noise
                kw = {"in", "of", "if", "then", "else", "let", "nat", "int",
                      "boolean", "string", "true", "false"}
                return [n for n in names if n.lower() not in kw and len(n) > 1]
    return []


def _parse_operator_def(text: str) -> tuple[str, list[str], str]:
    """Return (name, params, body) from an operator definition text."""
    m = re.match(r"^([A-Za-z_]\w*)\s*(\([^)]*\))?\s*==(?!=)\s*(.*)", text,
                 re.S)
    if not m:
        return ("", [], "")
    name = m.group(1)
    params_s = m.group(2) or ""
    body = m.group(3) if m.group(3) else ""
    params = [p.strip() for p in re.findall(r"[A-Za-z_]\w*", params_s)]
    return name, params, body


def _classify_operator(name: str, body: str) -> str:
    """Classify an operator as spec_meta, action, invariant, or predicate."""
    if name in SPEC_META_NAMES:
        return "spec_meta"
    if name in INVARIANT_SIGNALS:
        return "invariant"
    # Actions have primed variables (v')
    if re.search(r"\b\w+'\s*[=\\(]", body) or re.search(r"\b\w+'\s*==", body):
        return "action"
    # Temporal properties contain [] or <>
    if re.search(r"\[\]\s*[\[\(\\]|\<\>", body):
        return "invariant"
    return "predicate"


def _extract_reads_writes(body: str, variables: list[str]) -> tuple[set[str], set[str]]:
    """Return (reads, writes) sets of variable names from an operator body."""
    # Strip comments
    body = re.sub(r"\\\*[^\n]*", "", body)
    body = re.sub(r"\(\*.*?\*\)", "", body, flags=re.S)

    writes: set[str] = set()
    reads: set[str] = set()
    for var in variables:
        if re.search(rf"\b{re.escape(var)}'", body):
            writes.add(var)
        if re.search(rf"\b{re.escape(var)}\b", body):
            reads.add(var)
    # reads includes writes (the var appears unprimed too in most actions)
    # convention: reads = vars used unprimed, writes = vars used primed
    return reads, writes


def _extract_next_disjuncts(next_body: str) -> list[str]:
    """
    Extract action names from the Next operator body.
    Handles: \\/ A \\/ B  and  \\E x : A(x)  forms.
    """
    # Strip comments
    body = re.sub(r"\\\*[^\n]*", "", next_body)
    body = re.sub(r"\(\*.*?\*\)", "", body, flags=re.S)

    disjuncts: list[str] = []

    # Find operator names (capitalized or mixed) that appear as direct calls
    # Pattern: optional \E quantifiers, then ActionName optionally followed by (...)
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|$|\s*\\|$)",
                         body):
        cand = m.group(1)
        # Skip TLA+ keywords and structural words
        if cand in {"Next", "Spec", "Init", "Fairness", "vars", "WF",
                    "SF", "EXTENDS", "VARIABLES", "CONSTANTS", "ASSUME",
                    "BOOLEAN", "Nat", "Int", "Seq", "TRUE", "FALSE",
                    "UNCHANGED", "EXCEPT", "ENABLED", "IF", "THEN", "ELSE",
                    "LET", "IN", "CASE", "OTHER", "WITH"}:
            continue
        if re.match(r"^[A-Z][a-z]", cand) or re.match(r"^[a-z]", cand):
            if len(cand) > 1:
                disjuncts.append(cand)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for d in disjuncts:
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


def _extract_init_assigns(init_body: str, variables: list[str]) -> list[str]:
    """Extract variable names that appear in the Init operator body."""
    body = re.sub(r"\\\*[^\n]*", "", init_body)
    body = re.sub(r"\(\*.*?\*\)", "", body, flags=re.S)
    return [v for v in variables if re.search(rf"\b{re.escape(v)}\b", body)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_spec(path: str | Path) -> SpecGraph:
    """
    Parse a TLA+ spec file into a SpecGraph.

    The SpecGraph.g (NetworkX MultiDiGraph) has:
      - nodes with attrs: kind, name, text, params
      - edges with attrs: kind
    The SpecGraph.blocks list supports exact round-trip serialization.
    """
    path = Path(path)
    text = path.read_text()
    module_m = re.search(r"-{4,}\s*MODULE\s+(\w+)\s*-{4,}", text)
    module_name = module_m.group(1) if module_m else path.stem

    blocks = _split_blocks(text)
    variables = _extract_variables(blocks)

    sg = SpecGraph(module_name=module_name, blocks=blocks)
    sg.variables = variables
    g = sg.g

    # Add variable nodes
    for var in variables:
        g.add_node(var, kind="var", name=var, text=var, params=[])

    # Parse operator blocks
    op_nodes: dict[str, dict] = {}  # name -> attrs
    for idx, blk in enumerate(blocks):
        if blk.kind != "operator":
            continue
        name, params, body = _parse_operator_def(blk.text.strip())
        if not name:
            continue
        kind = _classify_operator(name, blk.text)
        g.add_node(name, kind=kind, name=name, text=blk.text,
                   params=params, body=body)
        op_nodes[name] = {"kind": kind, "body": body, "params": params}
        sg.op_block_idx[name] = idx

    # Add reads/writes edges from actions and predicates
    for name, attrs in op_nodes.items():
        if attrs["kind"] in ("action", "predicate"):
            reads, writes = _extract_reads_writes(attrs["body"], variables)
            for v in reads:
                if g.has_node(v):
                    g.add_edge(name, v, kind="reads")
            for v in writes:
                if g.has_node(v):
                    g.add_edge(name, v, kind="writes")

    # Add init_assigns edges from Init
    if "Init" in op_nodes:
        for v in _extract_init_assigns(op_nodes["Init"]["body"], variables):
            if g.has_node(v):
                g.add_edge("Init", v, kind="init_assigns")

    # Add next_disjunct edges from Next
    if "Next" in op_nodes:
        disjuncts = _extract_next_disjuncts(op_nodes["Next"]["body"])
        for d in disjuncts:
            if g.has_node(d) and g.nodes[d].get("kind") in ("action", "predicate"):
                g.add_edge("Next", d, kind="next_disjunct")

    # Add conjunct edges: actions that call named predicates/other actions
    all_ops = set(op_nodes.keys())
    for name, attrs in op_nodes.items():
        if attrs["kind"] != "action":
            continue
        body_clean = re.sub(r"\\\*[^\n]*", "", attrs["body"])
        body_clean = re.sub(r"\(\*.*?\*\)", "", body_clean, flags=re.S)
        for cand in re.findall(r"\b([A-Z][A-Za-z0-9_]*|[a-z][A-Za-z0-9_]+)\b",
                               body_clean):
            if (cand in all_ops and cand != name
                    and op_nodes[cand]["kind"] in ("predicate", "action")
                    and cand not in SPEC_META_NAMES):
                g.add_edge(name, cand, kind="conjuncts")

    return sg


def serialize_spec(sg: SpecGraph) -> str:
    """Reconstruct the TLA+ spec text from the SpecGraph's block list."""
    parts = []
    for blk in sg.blocks:
        parts.append(blk.text)
    result = "".join(parts)
    # Normalize trailing newline
    if not result.endswith("\n"):
        result += "\n"
    return result


def round_trip_test(path: str | Path) -> bool:
    """
    Parse spec at path and serialize back. Returns True if result is
    byte-for-byte identical to the original (after trailing-newline normalize).
    Prints diff on failure.
    """
    path = Path(path)
    original = path.read_text()
    if not original.endswith("\n"):
        original += "\n"

    sg = parse_spec(path)
    reconstructed = serialize_spec(sg)

    if original == reconstructed:
        return True

    # Report differences
    orig_lines = original.splitlines(keepends=True)
    recon_lines = reconstructed.splitlines(keepends=True)
    import difflib
    diff = list(difflib.unified_diff(orig_lines, recon_lines,
                                     fromfile="original",
                                     tofile="reconstructed",
                                     n=3))
    if diff:
        print(f"ROUND-TRIP DIFF for {path.name}:", file=sys.stderr)
        sys.stderr.writelines(diff[:60])
        if len(diff) > 60:
            print(f"  ... ({len(diff) - 60} more lines)", file=sys.stderr)
    return False


def graph_summary(sg: SpecGraph) -> str:
    """Return a human-readable summary of the spec graph."""
    g = sg.g
    lines = [f"MODULE {sg.module_name}"]
    lines.append(f"  variables ({len(sg.variables)}): {', '.join(sg.variables)}")

    for kind in ("action", "predicate", "invariant", "spec_meta"):
        nodes = [n for n, d in g.nodes(data=True) if d.get("kind") == kind]
        if nodes:
            lines.append(f"  {kind}s ({len(nodes)}): {', '.join(sorted(nodes))}")

    actions = [n for n, d in g.nodes(data=True) if d.get("kind") == "action"]
    for a in sorted(actions):
        writes = [v for _, v, d in g.out_edges(a, data=True)
                  if d.get("kind") == "writes"]
        reads = [v for _, v, d in g.out_edges(a, data=True)
                 if d.get("kind") == "reads"]
        lines.append(f"    {a}: writes={sorted(writes)}, reads={sorted(reads)}")

    next_d = [v for _, v, d in g.out_edges("Next", data=True)
              if d.get("kind") == "next_disjunct"] if g.has_node("Next") else []
    if next_d:
        lines.append(f"  next_disjuncts: {next_d}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="TLA+ ↔ NetworkX spec graph tool")
    ap.add_argument("--test", action="store_true",
                    help="Round-trip test all 9 corpus specs")
    ap.add_argument("--show", metavar="SPEC",
                    help="Print graph summary for a spec name or path")
    args = ap.parse_args()

    if args.test:
        passed = 0
        failed = 0
        for spec_name, spec_dir in SPEC_LIST:
            path = Path(spec_dir) / f"{spec_name}.tla"
            if not path.exists():
                print(f"  SKIP {spec_name} (not found)", file=sys.stderr)
                continue
            ok = round_trip_test(path)
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {spec_name}")
            if ok:
                passed += 1
            else:
                failed += 1
        print(f"\n{passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)

    if args.show:
        # Accept either a bare spec name or a path
        p = Path(args.show)
        if not p.exists():
            p = TLA_DIR / f"{args.show}.tla"
        if not p.exists():
            print(f"Spec not found: {args.show}", file=sys.stderr)
            sys.exit(1)
        sg = parse_spec(p)
        print(graph_summary(sg))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
