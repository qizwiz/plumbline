"""
tlc_to_forge — translate a plumbline detection finding (TLA+ shape +
target contract + TLC counterexample trace) into a runnable Foundry
test file.

This converts plumbline output from "leads worth investigating" into
"evidence worth paying for" — the universal quality bar across
Sherlock/Code4rena/Immunefi/client audits.

Per docs/research/IMMUNEFI_STRATEGY.md (3-0 verified): runnable
Hardhat/Foundry PoC against local mainnet fork is the universal 2026
submission standard. Prose-only PoCs are auto-rejected on Immunefi
and degrade contest judging on Sherlock/C4.

v1 STATUS:
  - Translator scaffold complete
  - ReentrancyDrain template emitted as v1, UNVERIFIED (forge test
    has not yet been run against a known target — that's the
    morning's first task)
  - Other 8 shape templates: TODO

Usage:
  python tools/tlc_to_forge.py \\
      --shape ReentrancyDrain \\
      --target-path src/PuppyRaffle.sol \\
      --target-contract PuppyRaffle \\
      --target-fn refund \\
      --target-fn-args "uint256 playerIndex" \\
      --target-fn-call-args "0" \\
      --out test/PoC_ReentrancyDrain.t.sol

  # Then in the target's Foundry project:
  forge test --match-test test_ReentrancyDrain_exploit -vvvv

See templates/foundry_poc/_README.md for the shape-to-template registry.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = HERE / "templates" / "foundry_poc"

# Registry: shape name → template filename + invariant name + default trace head.
# As more shapes get templates, add rows here.
SHAPE_TEMPLATES = {
    "ReentrancyDrain": {
        "template": "ReentrancyDrain.t.sol.template",
        "invariant": "ClaimedAtMostOnce",
        "default_trace_head": (
            "// State 0: slot=Live, paid=0, reentries=0\n"
            "//   Action: PreCheckBuggy(e)\n"
            "// State 1: slot=Calling, paid=TicketPrice, reentries=1\n"
            "//   Action: ReenterBuggy(e)\n"
            "// State 2: slot=Calling, paid=2*TicketPrice, reentries=2  ← INVARIANT VIOLATED"
        ),
    },
    # TODO: SignatureReplay, ERC4337StaticSigDoS, Uint64FeeOverflow,
    #       Create2NonIdempotent, PartialSignatureReplay,
    #       CrossWalletSigReplay, FlagBypassesValidationChain,
    #       ArbitraryFromApprovalTheft.
}


def load_template(shape: str) -> str:
    if shape not in SHAPE_TEMPLATES:
        raise KeyError(f"No PoC template for shape {shape!r}. "
                       f"Available: {sorted(SHAPE_TEMPLATES.keys())}")
    path = TEMPLATE_DIR / SHAPE_TEMPLATES[shape]["template"]
    if not path.exists():
        raise FileNotFoundError(f"Template missing: {path}. "
                                "See templates/foundry_poc/_README.md.")
    return path.read_text()


def substitute(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", str(value))
    # Detect unfilled placeholders (other than SETUP_DEPLOY_BLOCK which is
    # an intentional TODO marker).
    import re
    unfilled = re.findall(r"\{\{([A-Z_]+)\}\}", out)
    unfilled = [u for u in unfilled if u != "SETUP_DEPLOY_BLOCK"]
    if unfilled:
        sys.stderr.write(f"WARN: unfilled placeholders: {sorted(set(unfilled))}\n")
    return out


def translate(shape: str, target_path: str, target_contract: str,
              target_fn: str, target_fn_args: str = "",
              target_fn_call_args: str = "0",
              tlc_trace_head: str | None = None) -> str:
    template = load_template(shape)
    spec = SHAPE_TEMPLATES[shape]
    mapping = {
        "TARGET_PATH": target_path,
        "TARGET_CONTRACT": target_contract,
        "TARGET_FN": target_fn,
        "TARGET_FN_ARGS": target_fn_args,
        "TARGET_FN_CALL_ARGS": target_fn_call_args,
        "TLC_TRACE_HEAD": tlc_trace_head or spec["default_trace_head"],
        "INVARIANT_BROKEN": spec["invariant"],
        # Bounty-mode placeholders (unused for contest scope):
        "FORK_RPC_ENV": "$RPC_URL",
        "FORK_BLOCK": "19000000",
    }
    return substitute(template, mapping)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shape", required=True,
                    choices=sorted(SHAPE_TEMPLATES.keys()) + ["LIST"],
                    help="FailureMode shape from docs/tla/. Use LIST to "
                         "print available shapes and exit.")
    ap.add_argument("--target-path",
                    help="Solidity file path relative to forge root, "
                         "e.g., src/PuppyRaffle.sol")
    ap.add_argument("--target-contract",
                    help="Contract name, e.g., PuppyRaffle")
    ap.add_argument("--target-fn",
                    help="Vulnerable function name, e.g., refund")
    ap.add_argument("--target-fn-args", default="",
                    help="Function signature args, e.g., 'uint256 playerIndex'")
    ap.add_argument("--target-fn-call-args", default="0",
                    help="Function call-site args, e.g., '0' or 'playerIdx'")
    ap.add_argument("--trace-head",
                    help="First 6 lines of TLC counterexample (multi-line).")
    ap.add_argument("--out",
                    help="Output .t.sol path. If omitted, writes to stdout.")
    args = ap.parse_args()

    if args.shape == "LIST":
        print("Available PoC templates:")
        for s, spec in sorted(SHAPE_TEMPLATES.items()):
            avail = "✓" if (TEMPLATE_DIR / spec["template"]).exists() else "?"
            print(f"  {avail}  {s:<30} ({spec['template']})")
        print()
        print("9 TLA+ shapes total. 1 template shipped. 8 TODO.")
        return

    if not all([args.target_path, args.target_contract, args.target_fn]):
        ap.error("--target-path, --target-contract, --target-fn required "
                 "(unless --shape LIST)")

    output = translate(
        shape=args.shape,
        target_path=args.target_path,
        target_contract=args.target_contract,
        target_fn=args.target_fn,
        target_fn_args=args.target_fn_args,
        target_fn_call_args=args.target_fn_call_args,
        tlc_trace_head=args.trace_head,
    )

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(output)
        print(f"wrote → {args.out}", file=sys.stderr)
        print(f"  shape: {args.shape}", file=sys.stderr)
        print(f"  target: {args.target_contract}.{args.target_fn}",
              file=sys.stderr)
        print(file=sys.stderr)
        print("NEXT: drop into the target's Foundry project, run:",
              file=sys.stderr)
        print(f"  forge test --match-test test_{args.shape}_exploit -vvvv",
              file=sys.stderr)
        print("v1 unverified — manual fill needed in setUp() per TODO "
              "comments.", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
