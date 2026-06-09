"""
trace_to_forge — generalized template filler.

Takes a per-shape JSON manifest (tools/manifests/<target>-<shape>.json) and
emits a Foundry test from the universal template at
templates/foundry_poc/_universal.t.sol.template.

This replaces the per-shape .t.sol.template approach. Each new (shape, target)
pair becomes a ~10-line JSON manifest instead of a ~150-line Solidity file.

USAGE:
  python tools/trace_to_forge.py \\
      --manifest tools/manifests/puppy-raffle-ReentrancyDrain.json \\
      --out examples/puppy-raffle/test/Universal_ReentrancyDrain.t.sol

  cd examples/puppy-raffle
  forge test --match-path test/Universal_ReentrancyDrain.t.sol

VERIFIED end-to-end on 2026-06-09: emits a test that PASSES on the buggy
PuppyRaffle.refund and demonstrates the ClaimedAtMostOnce invariant
violation captured by the TLC counterexample of docs/tla/ReentrancyDrain.tla.

DESIGN:
  - Universal template uses {{PLACEHOLDERS}} for every variable section.
  - Manifest specifies: target, state vars, attacker contract structure,
    setUp body, trace replay body, invariant assertions, TLC trace head.
  - This script reads the manifest, formats each list as indented Solidity
    lines, fills the template, writes the file.

ADDING A NEW SHAPE:
  1. Write a manifest at tools/manifests/<target>-<shape>.json
  2. Run: python tools/trace_to_forge.py --manifest <path> --out <test path>
  3. Run forge test; iterate manifest on errors.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
UNIVERSAL_TEMPLATE = HERE / "templates" / "foundry_poc" / "_universal.t.sol.template"


def indent_lines(lines: list[str], spaces: int = 8) -> str:
    """Indent a list of Solidity lines for insertion into the template."""
    pad = " " * spaces
    return "\n".join(pad + line for line in lines)


def emit_attacker_contract(a: dict) -> str:
    if not a:
        return ""
    fields = "\n    ".join(a.get("fields", []))
    parts = [
        f"contract {a['name']} {{",
        f"    {fields}" if fields else "",
        f"    constructor({a['constructor_args']}) public {{",
        f"        {a['constructor_body']}",
        f"    }}",
        "",
        f"    function {a['trigger_fn']['name']}({a['trigger_fn']['args']}) external payable {{",
        f"        {a['trigger_fn']['body']}",
        f"    }}",
        "",
        f"    receive() external payable {{",
        f"        {a['receive_body']}",
        f"    }}",
        "}",
    ]
    return "\n".join(parts)


def emit_tlc_trace_comment(lines: list[str]) -> str:
    return "\n".join(f"// {line}" for line in lines)


def fill_template(manifest: dict) -> str:
    template = UNIVERSAL_TEMPLATE.read_text()
    target = manifest["target"]
    substitutions = {
        "PRAGMA": target.get("pragma", "^0.8.20"),
        "SHAPE_NAME": manifest["shape"],
        "TARGET_PATH": target["path"],
        "TARGET_CONTRACT": target["contract"],
        "TARGET_FN": target.get("target_fn", "(n/a)"),
        "TLA_SPEC_PATH": manifest.get("tla_spec_path", ""),
        "INVARIANT_NAME": manifest["invariant"],
        "TLC_TRACE_HEAD_COMMENT": emit_tlc_trace_comment(manifest.get("tlc_trace_head", [])),
        "ATTACKER_CONTRACT_BLOCK": emit_attacker_contract(manifest.get("attacker_contract", {})),
        "STATE_VAR_BLOCK": indent_lines(manifest.get("state_vars", []), spaces=4),
        "SETUP_BLOCK": indent_lines(manifest["setup_block"]),
        "TRACE_REPLAY_BLOCK": indent_lines(manifest["trace_replay_block"]),
        "INVARIANT_ASSERT_BLOCK": indent_lines(manifest["invariant_assert_block"]),
    }
    for k, v in substitutions.items():
        template = template.replace("{{" + k + "}}", str(v))
    # detect any unfilled placeholders
    import re
    leftover = re.findall(r"\{\{([A-Z_]+)\}\}", template)
    if leftover:
        sys.stderr.write(f"WARN: unfilled placeholders: {sorted(set(leftover))}\n")
    return template


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to <target>-<shape>.json manifest")
    ap.add_argument("--out", help="Output .t.sol path. If omitted, prints to stdout.")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    output = fill_template(manifest)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output)
        print(f"wrote → {args.out}", file=sys.stderr)
        print(f"  shape:     {manifest['shape']}", file=sys.stderr)
        print(f"  target:    {manifest['target']['contract']}.{manifest['target'].get('target_fn','?')}", file=sys.stderr)
        print(f"  invariant: {manifest['invariant']}", file=sys.stderr)
        print(file=sys.stderr)
        print("NEXT:", file=sys.stderr)
        print(f"  cd $(dirname {args.out})/..", file=sys.stderr)
        print(f"  forge test --match-path {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
