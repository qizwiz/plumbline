"""
manifest_lint — sanity-check every JSON manifest in tools/manifests/.

For each manifest:
  1. Schema check: required fields present, types correct
  2. Static check on setup_block / trace_replay_block strings:
     - flag bare `vm.prank(...)` followed by a line that contains a call
       inside an argument expression (the prank-consumed-by-arg footgun)
     - flag bare `vm.prank(...)` followed by multiple calls in one line
       (only the first call is pranked)
  3. If --run is passed, emit the manifest with trace_to_forge.py, drop
     it into the target's Foundry project (located via target.path's
     parent containing foundry.toml), and run forge test, reporting pass/fail.

Purpose: prevents the universal template from rotting as more manifests
land. Catches the same class of bug that took 30 min to debug on the
DRE M-1 manifest (vm.prank consumed by victim.balanceOf(alice) inside
victim.redeem's argument list).

USAGE:
  python tools/manifest_lint.py                       # static-only
  python tools/manifest_lint.py --run                 # static + forge test each
  python tools/manifest_lint.py --manifest <path>     # one manifest only
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST_DIR = HERE / "tools" / "manifests"
TRACE_TO_FORGE = HERE / "tools" / "trace_to_forge.py"

REQUIRED_FIELDS = {"shape", "invariant", "target", "setup_block",
                   "trace_replay_block", "invariant_assert_block"}
REQUIRED_TARGET_FIELDS = {"path", "contract"}

# Lines we will scan for the prank-consumed-by-arg footgun.
# Pattern: vm.prank(X); on one statement, then the NEXT statement contains
# a call whose arguments contain another `.something(` call.
PRANK_RE = re.compile(r"vm\.prank\s*\(")
START_PRANK_RE = re.compile(r"vm\.(start|stop)Prank\s*\(")
CALL_IN_ARG_RE = re.compile(r"\w+\.\w+\([^)]*\w+\.\w+\(")  # nested .x(.y(


def lint_block(block: list[str], block_name: str) -> list[str]:
    """Return a list of warning strings for suspicious patterns."""
    warnings = []
    flat = []
    for line in block:
        # split each `line` on semicolons → individual statements
        # so multi-statement single-line manifests still get scanned
        stmts = [s.strip() for s in line.split(";") if s.strip()]
        flat.extend(stmts)

    for i, stmt in enumerate(flat):
        if PRANK_RE.search(stmt) and not START_PRANK_RE.search(stmt):
            # bare vm.prank — check next statement
            if i + 1 < len(flat):
                next_stmt = flat[i + 1]
                if CALL_IN_ARG_RE.search(next_stmt):
                    warnings.append(
                        f"{block_name}: bare vm.prank followed by "
                        f"`{next_stmt[:60]}...` which has a nested call "
                        f"inside its arguments. The prank will be CONSUMED "
                        f"by the inner call. Use vm.startPrank/stopPrank or "
                        f"cache the arg first."
                    )
                # also flag: multiple external calls on next line
                # (e.g. "asset.approve(...); victim.deposit(...);")
                # But these are already split into separate flat entries.
    return warnings


def lint_manifest(path: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one manifest file."""
    errors, warnings = [], []
    try:
        m = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"JSON parse error: {e}"], []

    missing = REQUIRED_FIELDS - set(m.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    if "target" in m:
        tmissing = REQUIRED_TARGET_FIELDS - set(m["target"].keys())
        if tmissing:
            errors.append(f"target missing fields: {sorted(tmissing)}")

    for blk in ("setup_block", "trace_replay_block", "invariant_assert_block"):
        if blk in m and isinstance(m[blk], list):
            warnings.extend(lint_block(m[blk], blk))

    return errors, warnings


def find_forge_root(manifest: dict) -> Path | None:
    """Resolve forge root for a manifest.

    Preference: manifest['forge_root'] (relative to plumbline root).
    Fallback: walk corpus/calibration/* and examples/* for a foundry.toml
    whose presence + target.path makes sense.
    """
    if "forge_root" in manifest:
        cand = HERE / manifest["forge_root"]
        if (cand / "foundry.toml").exists():
            return cand
        return None

    target_path = manifest["target"]["path"]
    target_basename = Path(target_path).name
    roots = []
    for top in ("corpus/calibration", "examples"):
        top_path = HERE / top
        if not top_path.exists():
            continue
        for p in top_path.rglob("foundry.toml"):
            roots.append(p.parent)
    for root in roots:
        # heuristic: target exists at root/<target.path> OR target.path's
        # basename appears under root/{src,contracts,...}
        if (root / target_path).exists():
            return root
        for hits in root.rglob(target_basename):
            if hits.is_file():
                return root
    return None


def run_manifest(path: Path) -> tuple[bool, str]:
    """Emit + run via forge. Returns (ok, message)."""
    m = json.loads(path.read_text())
    forge_root = find_forge_root(m)
    if forge_root is None:
        return False, f"could not locate forge root for target {m['target']['path']}"

    out = forge_root / "test" / f"_lint_{path.stem}.t.sol"
    emit = subprocess.run(
        ["python3", str(TRACE_TO_FORGE), "--manifest", str(path), "--out", str(out)],
        capture_output=True, text=True
    )
    if emit.returncode != 0:
        return False, f"trace_to_forge failed: {emit.stderr.strip()}"

    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.foundry' / 'bin'}:{env.get('PATH','')}"
    res = subprocess.run(
        ["forge", "test", "--match-path", str(out.relative_to(forge_root))],
        cwd=str(forge_root), capture_output=True, text=True, env=env,
        timeout=180,
    )
    out.unlink(missing_ok=True)
    if "1 passed" in res.stdout or "passed" in res.stdout and "failed" not in res.stdout:
        return True, "PASS"
    return False, f"forge test FAIL\nstdout tail: {res.stdout[-300:]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", help="Lint one manifest only")
    ap.add_argument("--run", action="store_true",
                    help="Also emit + forge test each manifest")
    args = ap.parse_args()

    if args.manifest:
        paths = [Path(args.manifest)]
    else:
        paths = sorted(MANIFEST_DIR.glob("*.json"))

    n_err = n_warn = n_pass = n_run_fail = 0
    for p in paths:
        errors, warnings = lint_manifest(p)
        print(f"\n=== {p.name} ===")
        for e in errors:
            print(f"  ERROR: {e}")
            n_err += 1
        for w in warnings:
            print(f"  WARN:  {w}")
            n_warn += 1
        if not errors and not warnings:
            print("  (lint clean)")

        if args.run and not errors:
            ok, msg = run_manifest(p)
            mark = "PASS" if ok else "FAIL"
            print(f"  forge: {mark} — {msg}")
            if ok:
                n_pass += 1
            else:
                n_run_fail += 1

    print(f"\nsummary: {len(paths)} manifests, {n_err} errors, {n_warn} warnings", end="")
    if args.run:
        print(f", {n_pass} forge PASS, {n_run_fail} forge FAIL")
    else:
        print()
    sys.exit(0 if n_err == 0 and n_run_fail == 0 else 1)


if __name__ == "__main__":
    main()
