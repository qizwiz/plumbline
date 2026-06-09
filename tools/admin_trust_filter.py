"""
admin_trust_filter.py — mechanical admin-trust pattern filter for plumbline leads.

Sherlock's admin-trust rule: functions callable ONLY by protocol admins/owners
are out of scope by default. This filter mechanically detects such functions
and downgrades their leads to "REVIEW: admin-trust".

Checks (in order, first match wins):
  1. Function declaration has an only*/requiresAuth/restricted modifier
  2. Function body has require(msg.sender == <var>) or if-revert guard
  3. Function operates on an immutable address (set in constructor, no setter)
  4. Function operates on an address variable whose only setter is admin-gated

Usage:
  python tools/admin_trust_filter.py union-leads.json \\
      --scope-dir <scope> [--audit-log rejected.json] [--no-filter]

Outputs:
  - stdout: JSON list of all leads (admin-trust leads have confidence="REVIEW:admin-trust")
  - --audit-log: JSON of leads that were downgraded, with reasons
  - --rejected-section: print a REJECTED section to stderr for JH to audit
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# ── access-control modifier patterns ────────────────────────────────────────
# Matches: onlyOwner, onlyRole(...), onlyAdmin, requiresAuth, restricted, etc.
_MOD_RE = re.compile(
    r'\b(only\w+|requiresAuth|restricted|protected|authorized|nonReentrant'
    r'|onlyGov|onlyDAO|onlyOperator|onlyMinter|onlyBurner|onlyManager'
    r'|onlyGuardian|onlyStrategist|onlyVault|onlyKeeper)\b',
    re.I,
)
# We want the SECURITY-relevant subset, not all modifiers (nonReentrant is not admin-trust)
_ADMIN_TRUST_MODS = re.compile(
    r'\b(only(?!NonReentrant)\w+|requiresAuth|restricted(?!ToRole)|authorized)\b',
    re.I,
)

# ── inline require/revert guard ──────────────────────────────────────────────
_REQUIRE_SENDER = re.compile(
    r'require\s*\(\s*msg\.sender\s*==\s*(\w+)', re.I)
_IF_REVERT_SENDER = re.compile(
    r'if\s*\(\s*msg\.sender\s*!=\s*(\w+)\s*\)\s*(revert|_)', re.I)
_CHECK_OWNER = re.compile(r'\b(_checkOwner|_onlyAdmin|_onlyOwner|_assertOwner)\s*\(', re.I)

# ── immutable / constructor-set address patterns ─────────────────────────────
_IMMUTABLE_ADDR = re.compile(
    r'\baddress\b.*?\bimmutable\b.*?(\w+)\s*;', re.I)
_CONSTRUCTOR_SET = re.compile(
    r'constructor\s*\(.*?\)\s*\{([^}]+)\}', re.S)

# ── admin-gated address setter ───────────────────────────────────────────────
# Detects patterns like:
#   function setFoo(address _x) external onlyOwner { foo = _x; }
_ADMIN_SETTER = re.compile(
    r'function\s+set\w+\s*\(.*?address.*?\).*?only\w+.*?\{[^}]*\}', re.S | re.I)

# ── view/pure function detection ─────────────────────────────────────────────
_VIEW_PURE = re.compile(r'\b(view|pure)\b', re.I)


# ── Solidity parsing utilities ───────────────────────────────────────────────

def _extract_function_text(sol_text: str, func_name: str) -> str | None:
    """Return the full text of function func_name from sol_text, or None."""
    start_pat = re.compile(
        r'\bfunction\s+' + re.escape(func_name) + r'\s*\(', re.M)
    m = start_pat.search(sol_text)
    if not m:
        return None
    # Grab from 'function' keyword to the closing brace of the body
    start = m.start()
    brace_pos = sol_text.find('{', m.end())
    if brace_pos == -1:
        return sol_text[start:]
    depth = 0
    pos = brace_pos
    while pos < len(sol_text):
        ch = sol_text[pos]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return sol_text[start: pos + 1]
        pos += 1
    return sol_text[start:]


def _function_header(func_text: str) -> str:
    """Return everything up to but not including the opening brace."""
    brace = func_text.find('{')
    return func_text[:brace] if brace != -1 else func_text


def _function_body(func_text: str) -> str:
    """Return everything inside the outermost braces."""
    brace = func_text.find('{')
    return func_text[brace:] if brace != -1 else ""


# ── admin-set address detection ──────────────────────────────────────────────

def _admin_set_addresses(sol_text: str) -> set[str]:
    """Return set of state variable names whose only setters are admin-gated."""
    admin_vars: set[str] = set()
    for m in _ADMIN_SETTER.finditer(sol_text):
        body = m.group(0)
        # Extract the variable being assigned
        assignments = re.findall(r'(\w+)\s*=\s*\w+\s*;', body)
        admin_vars.update(assignments)
    # Also flag immutable addresses
    for m in _IMMUTABLE_ADDR.finditer(sol_text):
        admin_vars.add(m.group(1))
    return admin_vars


def _immutable_addresses(sol_text: str) -> set[str]:
    """Return names of immutable address state variables."""
    return {m.group(1) for m in _IMMUTABLE_ADDR.finditer(sol_text)}


# ── per-function trust check ─────────────────────────────────────────────────

def _check_function(func_text: str, sol_text: str) -> tuple[bool, str, str]:
    """Return (is_filtered, tag, reason). tag is 'admin-trust' or 'view-fn'."""
    header = _function_header(func_text)
    body = _function_body(func_text)

    # Check 1: explicit modifier
    mod_match = _ADMIN_TRUST_MODS.search(header)
    if mod_match:
        return True, "admin-trust", f"modifier {mod_match.group(1)}"

    # Check 2: inline require/revert guard
    rq = _REQUIRE_SENDER.search(body)
    if rq:
        return True, "admin-trust", f"require(msg.sender == {rq.group(1)})"
    rv = _IF_REVERT_SENDER.search(body)
    if rv:
        return True, "admin-trust", f"if(msg.sender != {rv.group(1)}) revert"
    if _CHECK_OWNER.search(body):
        return True, "admin-trust", "_checkOwner() / _onlyAdmin() guard"

    # Check 3: all external calls target admin-set addresses
    admin_vars = _admin_set_addresses(sol_text)
    external_calls = re.findall(r'\b(\w+)\.(call|transfer|send|execute)\s*\(', body)
    if external_calls:
        targets = {c[0] for c in external_calls}
        if targets and targets.issubset(admin_vars):
            return True, "admin-trust", f"calls only admin-set address(es): {', '.join(sorted(targets))}"

    # Check 4: view/pure function — not state-changing; H/M value-loss bugs
    # require a state mutation path. View/pure leads are typically Low/Info.
    if _VIEW_PURE.search(header):
        return True, "view-fn", "view/pure — not state-changing (typically Low/Info scope)"

    return False, "", ""


# ── file discovery ────────────────────────────────────────────────────────────

def _find_sol_file(scope_dir: Path, contract_name: str) -> Path | None:
    """Search scope_dir for a .sol file containing contract <contract_name>."""
    for sol in scope_dir.rglob("*.sol"):
        try:
            text = sol.read_text(errors="replace")
        except OSError:
            continue
        if re.search(r'\bcontract\s+' + re.escape(contract_name) + r'\b', text):
            return sol
    # Fallback: filename match
    for sol in scope_dir.rglob("*.sol"):
        if sol.stem.lower() == contract_name.lower():
            return sol
    return None


def _parse_location(location: str) -> tuple[str | None, str | None]:
    """Parse 'Contract.fn', 'Contract::fn', 'path/to/File.sol' → (contract, fn)."""
    for sep in ("::", "."):
        if sep in location:
            parts = location.rsplit(sep, 1)
            contract = parts[0].strip().split("/")[-1]  # drop any path prefix
            func = parts[1].strip()
            return contract, func
    # Just a contract or path
    if location.endswith(".sol"):
        return Path(location).stem, None
    return location, None


# ── main filter ───────────────────────────────────────────────────────────────

def filter_leads(leads: list[dict], scope_dir: Path,
                 no_filter: bool = False) -> tuple[list[dict], list[dict]]:
    """
    Returns (filtered_leads, rejected_leads).

    filtered_leads: all leads; admin-trust ones have confidence="REVIEW:admin-trust"
    rejected_leads: subset that were downgraded, with 'admin_trust_reason' added
    """
    if no_filter:
        return leads, []

    filtered: list[dict] = []
    rejected: list[dict] = []

    for lead in leads:
        location = lead.get("location", "")
        if not location:
            filtered.append(lead)
            continue

        contract_name, func_name = _parse_location(location)

        # If no function name in location, skip the check
        if not func_name:
            filtered.append(lead)
            continue

        sol_file = _find_sol_file(scope_dir, contract_name) if contract_name else None
        if sol_file is None:
            # Can't resolve file → pass through unchanged
            filtered.append(lead)
            continue

        try:
            sol_text = sol_file.read_text(errors="replace")
        except OSError:
            filtered.append(lead)
            continue

        func_text = _extract_function_text(sol_text, func_name)
        if func_text is None:
            filtered.append(lead)
            continue

        is_filtered, tag, reason = _check_function(func_text, sol_text)
        if is_filtered:
            out = dict(lead)
            out["confidence"] = f"REVIEW:{tag}"
            out["admin_trust_reason"] = reason
            filtered.append(out)
            rejected.append(out)
        else:
            filtered.append(lead)

    return filtered, rejected


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("union_leads", help="Path to union-leads.json")
    ap.add_argument("--scope-dir", required=True,
                    help="Root directory containing .sol files")
    ap.add_argument("--audit-log", default=None,
                    help="Write rejected leads to this JSON file")
    ap.add_argument("--rejected-section", action="store_true",
                    help="Print REJECTED section to stderr")
    ap.add_argument("--no-filter", action="store_true",
                    help="Pass all leads through unchanged (bypass filter)")
    args = ap.parse_args()

    leads_path = Path(args.union_leads)
    scope_dir = Path(args.scope_dir).resolve()

    leads = json.loads(leads_path.read_text())
    filtered, rejected = filter_leads(leads, scope_dir, no_filter=args.no_filter)

    print(json.dumps(filtered, indent=2))

    print(f"\n[admin_trust_filter] {len(leads)} in → "
          f"{len(leads) - len(rejected)} pass-through + "
          f"{len(rejected)} downgraded to REVIEW:admin-trust",
          file=sys.stderr)

    if args.audit_log:
        Path(args.audit_log).write_text(json.dumps(rejected, indent=2))
        print(f"[admin_trust_filter] audit log → {args.audit_log}", file=sys.stderr)

    if args.rejected_section and rejected:
        print("\n=== REJECTED — admin-trust scope ===", file=sys.stderr)
        for r in rejected:
            loc = r.get("location", "?")
            reason = r.get("admin_trust_reason", "?")
            claim = r.get("claim") or r.get("raw", "?")
            print(f"  • {loc}: {claim[:80]}  [{reason}]", file=sys.stderr)


if __name__ == "__main__":
    main()
