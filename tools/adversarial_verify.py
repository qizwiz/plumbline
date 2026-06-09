"""
adversarial_verify.py — mechanical adversarial checks for HIGH-confidence leads.

Runs three mechanical checks on each HIGH/CASCADE-CONFIRM lead:

  1. ACCESS_CONTROL: Is the entry-point function gated by onlyRole/onlyOwner?
     → If yes, Sherlock's admin-trust scope rule likely excludes it.

  2. ADMIN_SET_CALL: Does the function's only external call target an
     admin-set address (immutable, or setter protected by onlyOwner/onlyRole)?
     → If yes, the attack vector requires admin cooperation → out of scope.

  3. ATOMIC_INIT: For any lead claiming "front-run initializer" or "unprotected
     initializer": does the deployment script pass initData to an ERC1967Proxy
     or use initialize() in a single transaction?
     → If yes, the race window doesn't exist → CONFIRM is vacuous.

If ANY check fires → downgrade confidence to "REVIEW:adversarial" and record
which check fired + short reason.

NON-CONFIRM leads are passed through unchanged.

Usage:
  python tools/adversarial_verify.py union-leads.json \\
      --scope-dir <scope> [--scripts-dir <deploy>] [--audit-log rejected.json]

Outputs:
  stdout: JSON list of all leads (downgraded ones have confidence="REVIEW:adversarial")
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# ── regex patterns ────────────────────────────────────────────────────────────

_ADMIN_MOD = re.compile(
    r'\b(only(?!NonReentrant)\w+|requiresAuth|restricted(?!ToRole)|authorized'
    r'|onlyGov|onlyDAO|onlyOperator|onlyMinter|onlyBurner|onlyManager'
    r'|onlyGuardian|onlyStrategist|onlyVault|onlyKeeper)\b',
    re.I,
)
_REQUIRE_SENDER = re.compile(r'require\s*\(\s*msg\.sender\s*==\s*(\w+)', re.I)
_IF_REVERT_SENDER = re.compile(r'if\s*\(\s*msg\.sender\s*!=\s*(\w+)\s*\)\s*(revert|_)', re.I)
_CHECK_OWNER = re.compile(r'\b(_checkOwner|_onlyAdmin|_onlyOwner|_assertOwner)\s*\(', re.I)

# Admin-only setter: function setX(address ...) external onlyX { var = ... }
_ADMIN_SETTER = re.compile(
    r'function\s+set\w+\s*\([^)]*address[^)]*\)[^{]*only\w+[^{]*\{([^}]+)\}', re.S | re.I)
_IMMUTABLE_ADDR = re.compile(r'\baddress\b[^;]*\bimmutable\b[^;]*\b(\w+)\s*;', re.I)

# Initializer concern keywords in claim/why text
_INIT_KEYWORDS = re.compile(
    r'\b(initiali[sz]|front.?run|race\s+condition|proxy\s+init|unprotected\s+init)\b', re.I)

# ERC1967Proxy / TransparentUpgradeableProxy atomic init patterns in scripts
# Handles: new ERC1967Proxy{salt:...}(impl, initData) and abi.encodeWithSelector/encodeCall
_PROXY_INIT_RE = re.compile(
    r'(?:'
    r'ERC1967Proxy|TransparentUpgradeableProxy|UUPSUpgradeable'
    r')[^;]*?(?:initData|abi\.encode(?:WithSelector|Call)[^;]*?initiali[sz])'
    r'|abi\.encode(?:WithSelector|Call)[^;]*?\.initialize\b',
    re.I | re.S,
)
_SINGLE_INIT_CALL = re.compile(
    r'(new\s+\w+|deploy)\s*\([^)]*\)\s*;[^;]*\.initialize\s*\(',
    re.I | re.S,
)


# ── Solidity helpers ──────────────────────────────────────────────────────────

def _extract_function_text(sol_text: str, func_name: str) -> str | None:
    start_pat = re.compile(r'\bfunction\s+' + re.escape(func_name) + r'\s*\(', re.M)
    m = start_pat.search(sol_text)
    if not m:
        return None
    start = m.start()
    brace_pos = sol_text.find('{', m.end())
    if brace_pos == -1:
        return sol_text[start:]
    depth, pos = 0, brace_pos
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
    brace = func_text.find('{')
    return func_text[:brace] if brace != -1 else func_text


def _function_body(func_text: str) -> str:
    brace = func_text.find('{')
    return func_text[brace:] if brace != -1 else ""


def _admin_set_addresses(sol_text: str) -> set[str]:
    admin_vars: set[str] = set()
    for m in _ADMIN_SETTER.finditer(sol_text):
        assignments = re.findall(r'(\w+)\s*=\s*\w+\s*;', m.group(1))
        admin_vars.update(assignments)
    for m in _IMMUTABLE_ADDR.finditer(sol_text):
        admin_vars.add(m.group(1))
    return admin_vars


# ── file discovery ─────────────────────────────────────────────────────────────

def _find_sol_file(scope_dir: Path, contract_name: str) -> Path | None:
    for sol in scope_dir.rglob("*.sol"):
        try:
            text = sol.read_text(errors="replace")
        except OSError:
            continue
        if re.search(r'\bcontract\s+' + re.escape(contract_name) + r'\b', text):
            return sol
    for sol in scope_dir.rglob("*.sol"):
        if sol.stem.lower() == contract_name.lower():
            return sol
    return None


def _parse_location(location: str) -> tuple[str | None, str | None]:
    for sep in ("::", "."):
        if sep in location:
            parts = location.rsplit(sep, 1)
            contract = parts[0].strip().split("/")[-1]
            func = parts[1].strip()
            return contract, func
    if location.endswith(".sol"):
        return Path(location).stem, None
    return location, None


# ── three mechanical checks ───────────────────────────────────────────────────

def _check_access_control(func_text: str) -> tuple[bool, str]:
    """Check 1: is the entry point gated by admin access control?"""
    header = _function_header(func_text)
    body = _function_body(func_text)
    m = _ADMIN_MOD.search(header)
    if m:
        return True, f"modifier {m.group(1)} in function header"
    rq = _REQUIRE_SENDER.search(body)
    if rq:
        return True, f"require(msg.sender == {rq.group(1)}) guard"
    rv = _IF_REVERT_SENDER.search(body)
    if rv:
        return True, f"if(msg.sender != {rv.group(1)}) revert guard"
    if _CHECK_OWNER.search(body):
        return True, "_checkOwner() / _onlyAdmin() guard"
    return False, ""


def _check_admin_set_call(func_text: str, sol_text: str) -> tuple[bool, str]:
    """Check 2: does the function only call admin-set external addresses?"""
    body = _function_body(func_text)
    external_calls = re.findall(r'\b(\w+)\.(call|transfer|send|execute|deposit|withdraw)\s*\(', body)
    if not external_calls:
        return False, ""
    targets = {c[0] for c in external_calls}
    admin_vars = _admin_set_addresses(sol_text)
    if targets and targets.issubset(admin_vars):
        return True, f"external call targets admin-set address(es): {', '.join(sorted(targets))}"
    return False, ""


def _check_atomic_init(lead: dict, scripts_dir: Path | None,
                       func_name: str | None = None) -> tuple[bool, str]:
    """Check 3: for initializer-concern leads, is deployment script atomic?"""
    claim_text = " ".join([
        lead.get("claim", ""),
        lead.get("why", ""),
        lead.get("raw", ""),
    ])
    # Also trigger when the function itself is named "initialize" — cascade leads
    # don't always mention front-run in the claim text, but the risk is the same.
    if not _INIT_KEYWORDS.search(claim_text) and func_name != "initialize":
        return False, ""

    # No scripts dir → we can't confirm atomic, but can't refute either
    if scripts_dir is None or not scripts_dir.exists():
        return False, ""

    script_files = list(scripts_dir.rglob("*.sol")) + list(scripts_dir.rglob("*.ts")) + \
                   list(scripts_dir.rglob("*.js"))
    for sf in script_files:
        try:
            text = sf.read_text(errors="replace")
        except OSError:
            continue
        if _PROXY_INIT_RE.search(text) or _SINGLE_INIT_CALL.search(text):
            return True, (f"deployment script {sf.name} passes initData or chains "
                          f"deploy+initialize atomically → no front-run window")
    return False, ""


# ── per-lead verifier ─────────────────────────────────────────────────────────

def _verify_lead(lead: dict, scope_dir: Path,
                 scripts_dir: Path | None) -> tuple[dict, bool, str]:
    """
    Returns (updated_lead, was_downgraded, reason).
    Only HIGH-confidence leads are checked; others pass through.
    """
    if lead.get("confidence") not in ("HIGH", "CASCADE"):
        return lead, False, ""

    location = lead.get("location", "")
    contract_name, func_name = _parse_location(location) if location else (None, None)

    func_text = sol_text = None
    if contract_name and func_name:
        sol_file = _find_sol_file(scope_dir, contract_name)
        if sol_file:
            try:
                sol_text = sol_file.read_text(errors="replace")
                func_text = _extract_function_text(sol_text, func_name)
            except OSError:
                pass

    reasons: list[str] = []

    if func_text and sol_text:
        fired, reason = _check_access_control(func_text)
        if fired:
            reasons.append(f"[ACCESS_CONTROL] {reason}")
        fired, reason = _check_admin_set_call(func_text, sol_text)
        if fired:
            reasons.append(f"[ADMIN_SET_CALL] {reason}")

    fired, reason = _check_atomic_init(lead, scripts_dir, func_name=func_name)
    if fired:
        reasons.append(f"[ATOMIC_INIT] {reason}")

    if reasons:
        out = dict(lead)
        out["confidence"] = "REVIEW:adversarial"
        out["adversarial_reasons"] = reasons
        return out, True, "; ".join(reasons)

    return lead, False, ""


# ── main ──────────────────────────────────────────────────────────────────────

def verify_leads(leads: list[dict], scope_dir: Path,
                 scripts_dir: Path | None = None,
                 no_filter: bool = False) -> tuple[list[dict], list[dict]]:
    """
    Returns (all_leads_with_downgrades, downgraded_subset).
    """
    if no_filter:
        return leads, []

    out: list[dict] = []
    downgraded: list[dict] = []
    for lead in leads:
        updated, was_down, reason = _verify_lead(lead, scope_dir, scripts_dir)
        out.append(updated)
        if was_down:
            downgraded.append(updated)
    return out, downgraded


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("union_leads", help="Path to union-leads.json")
    ap.add_argument("--scope-dir", required=True,
                    help="Root directory containing .sol files")
    ap.add_argument("--scripts-dir", default=None,
                    help="Deployment scripts directory (optional; script/ or deploy/)")
    ap.add_argument("--audit-log", default=None,
                    help="Write downgraded leads to this JSON file")
    ap.add_argument("--no-filter", action="store_true",
                    help="Pass all leads through unchanged")
    args = ap.parse_args()

    scope_dir = Path(args.scope_dir).resolve()
    scripts_dir = Path(args.scripts_dir).resolve() if args.scripts_dir else None

    leads = json.loads(Path(args.union_leads).read_text())
    verified, downgraded = verify_leads(leads, scope_dir, scripts_dir,
                                        no_filter=args.no_filter)
    print(json.dumps(verified, indent=2))

    n_high = sum(1 for l in leads if l.get("confidence") in ("HIGH", "CASCADE"))
    print(f"\n[adversarial_verify] {n_high} HIGH leads checked → "
          f"{len(downgraded)} downgraded to REVIEW:adversarial, "
          f"{n_high - len(downgraded)} survive",
          file=sys.stderr)

    if downgraded:
        print("\n=== ADVERSARIALLY REJECTED ===", file=sys.stderr)
        for d in downgraded:
            loc = d.get("location", "?")
            reasons = d.get("adversarial_reasons", [])
            claim = (d.get("claim") or d.get("raw", "?"))[:80]
            print(f"  • {loc}: {claim}", file=sys.stderr)
            for r in reasons:
                print(f"      {r}", file=sys.stderr)

    if args.audit_log:
        Path(args.audit_log).write_text(json.dumps(downgraded, indent=2))
        print(f"[adversarial_verify] audit log → {args.audit_log}", file=sys.stderr)


if __name__ == "__main__":
    main()
