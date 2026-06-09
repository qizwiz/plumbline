"""
manifest_from_poc — extract a draft universal-template manifest from an
existing PoC Foundry test file.

Use this to compound the corpus: every PoC test you write or import can
become a registered manifest with ~5 minutes of cleanup instead of
starting from scratch.

The extractor does crude regex parsing — it surfaces the imports, state
vars, setUp body, and the first non-setUp test function body. Human
cleanup needed:
  - split `setUp` body across `setup_block` vs initial `trace_replay_block`
    if the test body doesn't replay actions itself
  - choose a `shape` from docs/tla/ (extractor guesses from the test file name)
  - choose an `invariant` (extractor leaves a TODO)
  - fix any pragma differences

USAGE:
  python tools/manifest_from_poc.py \\
      --poc corpus/calibration/.../test/PoC_X.t.sol \\
      --shape PausedDistributorPricingAsymmetry \\
      --target dreUSDs --target-path ../contracts/dreUSDs.sol \\
      --forge-root corpus/calibration/.../dreusd \\
      --out tools/manifests/dre-X.json

If --shape is omitted, the extractor guesses from the PoC filename
(PoC_X.t.sol → X).

After emit, run:
  python tools/manifest_lint.py --manifest <out> --run
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# Crude regex parsers; designed to extract draft material a human will edit.
IMPORT_RE   = re.compile(r"^import\s+\{[^}]+\}\s+from\s+\"[^\"]+\";\s*$", re.M)
PRAGMA_RE   = re.compile(r"^pragma\s+solidity\s+([^;]+);", re.M)
CONTRACT_DECL_RE = re.compile(r"^contract\s+(\w+)\s+is\s+[\w,\s]+\{$", re.M)
SETUP_RE    = re.compile(r"function\s+setUp\s*\(\s*\)\s+(?:public|external)\s*\{")
TESTFN_RE   = re.compile(r"function\s+(test_\w+)\s*\(\s*\)\s+(?:public|external)\s*\{")
STATE_VAR_RE = re.compile(r"^\s{4}((?:address|uint\d*|bool|bytes\d*|string|mapping)[^{}]*?;)\s*$", re.M)


def find_balanced_block(src: str, open_pos: int) -> tuple[int, int]:
    """Given pos of an `{`, return (body_start, body_end) of the matched block."""
    depth = 1
    i = open_pos + 1
    body_start = i
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{": depth += 1
        elif c == "}": depth -= 1
        i += 1
    return body_start, i - 1


def extract_fn_body(src: str, fn_re: re.Pattern) -> str | None:
    m = fn_re.search(src)
    if not m:
        return None
    open_brace = src.find("{", m.start())
    if open_brace < 0:
        return None
    s, e = find_balanced_block(src, open_brace)
    return src[s:e].strip()


def split_lines(body: str | None) -> list[str]:
    if not body:
        return []
    # take each non-empty stripped line; do NOT collapse multi-statement lines.
    return [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poc", required=True, help="Path to PoC_X.t.sol file")
    ap.add_argument("--shape", help="Shape name (guesses from filename if omitted)")
    ap.add_argument("--target", required=True, help="Target contract name")
    ap.add_argument("--target-path", required=True, help="Target source path (relative to forge root)")
    ap.add_argument("--target-fn", default="?", help="Vulnerable function name")
    ap.add_argument("--forge-root", required=True, help="forge_root (relative to plumbline root)")
    ap.add_argument("--out", required=True, help="Output manifest JSON path")
    args = ap.parse_args()

    src = Path(args.poc).read_text()

    pragma_m = PRAGMA_RE.search(src)
    pragma = pragma_m.group(1).strip() if pragma_m else "^0.8.20"

    shape = args.shape
    if not shape:
        # PoC_PausedDistributorUnfairWithdraw.t.sol → PausedDistributorUnfairWithdraw
        stem = Path(args.poc).stem.removesuffix(".t")
        shape = stem.removeprefix("PoC_") or stem

    # Imports (excluding Test + target — those are baked into the template)
    imports = [m.group(0).strip() for m in IMPORT_RE.finditer(src)]
    extra_imports = [
        imp for imp in imports
        if "forge-std/Test.sol" not in imp and args.target not in imp
    ]

    # State vars — anything at 4-space indent in the test contract scope.
    # This is best-effort; a human will likely trim.
    state_vars = [m.group(1).strip() for m in STATE_VAR_RE.finditer(src)]

    # Bodies
    setup_body  = extract_fn_body(src, SETUP_RE)
    testfn_body = extract_fn_body(src, TESTFN_RE)

    manifest = {
        "shape": shape,
        "forge_root": args.forge_root,
        "tla_spec_path": f"docs/tla/{shape}.tla",
        "invariant": "TODO_INVARIANT_NAME",
        "target": {
            "path": args.target_path,
            "contract": args.target,
            "target_fn": args.target_fn,
            "pragma": pragma,
        },
        "state_vars":            state_vars,
        "attacker_contract":     None,
        "setup_block":           split_lines(setup_body),
        "trace_replay_block":    split_lines(testfn_body),
        "invariant_assert_block":[
            "// TODO: derive from TLA+ INVARIANT statement",
            "emit log(\"<INVARIANT> VIOLATED: <reason>\");"
        ],
        "tlc_trace_head": ["// TODO: paste TLC counterexample trace head"],
        "extra_imports": extra_imports,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))

    n_warn = 0
    print(f"wrote draft manifest → {out}", file=sys.stderr)
    print(f"  shape:      {shape}", file=sys.stderr)
    print(f"  pragma:     {pragma}", file=sys.stderr)
    print(f"  state_vars: {len(state_vars)} extracted", file=sys.stderr)
    print(f"  setup:      {len(split_lines(setup_body))} lines", file=sys.stderr)
    print(f"  trace:      {len(split_lines(testfn_body))} lines", file=sys.stderr)
    print(f"  imports:    {len(extra_imports)} extra", file=sys.stderr)
    if not testfn_body:
        print(f"  WARN: no test_<fn>() body found; manifest's trace_replay_block is empty", file=sys.stderr)
        n_warn += 1
    print(file=sys.stderr)
    print("NEXT: edit the manifest:", file=sys.stderr)
    print(f"  1. fill in `invariant` (from docs/tla/{shape}.tla)", file=sys.stderr)
    print(f"  2. trim state_vars (extractor over-includes)", file=sys.stderr)
    print(f"  3. fix vm.prank → vm.startPrank/stopPrank for multi-call blocks", file=sys.stderr)
    print(f"  4. paste 6-state TLC trace head into tlc_trace_head", file=sys.stderr)
    print(f"  5. write the invariant assertion", file=sys.stderr)
    print(f"  6. run: python3 tools/manifest_lint.py --manifest {out} --run", file=sys.stderr)
    sys.exit(0 if n_warn == 0 else 1)


if __name__ == "__main__":
    main()
