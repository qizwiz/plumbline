# tlc_to_forge — PoC templates

One Foundry-test template per FailureMode shape. The translator
`tools/tlc_to_forge.py` selects the matching template, substitutes
target contract path + function name + parameters from the TLC
counterexample, and emits a runnable `.t.sol` file.

## Status

| shape | template | status |
|---|---|---|
| ReentrancyDrain | `ReentrancyDrain.t.sol.template` | **v1.1 VERIFIED** — `forge test` PASS on puppy-raffle H-1 (drains 3 ETH via 2 re-entries; matches TLC trace) |
| SignatureReplay | `SignatureReplay.t.sol.template` | **v1 unverified** — template written, follows same scaffolding as ReentrancyDrain; per-target setUp() helpers needed for verification on boss-bridge (OZ version mismatch in that target) |
| ERC4337StaticSigDoS | — | TODO |
| Uint64FeeOverflow | — | TODO |
| Create2NonIdempotent | — | TODO |
| PartialSignatureReplay | — | TODO |
| CrossWalletSigReplay | — | TODO |
| FlagBypassesValidationChain | — | TODO |
| ArbitraryFromApprovalTheft | — | TODO |

## Architecture

Each template is a string-interpolation skeleton. The translator
fills these placeholders:

| placeholder | from |
|---|---|
| `{{TARGET_PATH}}` | scope contract file (relative to forge root) |
| `{{TARGET_CONTRACT}}` | the vulnerable contract name |
| `{{TARGET_FN}}` | the vulnerable function (e.g., `refund`) |
| `{{TARGET_FN_ARGS}}` | the function signature args (e.g., `uint256 playerIndex`) |
| `{{TARGET_FN_CALL_ARGS}}` | call-site args (e.g., `0`) |
| `{{TLC_TRACE_HEAD}}` | first 6 lines of TLC counterexample for the @notice block |
| `{{INVARIANT_BROKEN}}` | invariant name from TLA+ spec (e.g., `ClaimedAtMostOnce`) |
| `{{IMPACT_AMOUNT_USD}}` | quantitative impact (Sherlock format) — auditor fills |
| `{{FORK_RPC_ENV}}` | env var for fork RPC URL (Immunefi: must be local fork) |
| `{{FORK_BLOCK}}` | mainnet block to fork from (for Immunefi/live targets) |

For contest scope (Sherlock/C4): `{{FORK_RPC_ENV}}` and `{{FORK_BLOCK}}` are unused — test runs against contract instances deployed in `setUp()`.

For bounty scope (Immunefi): the test forks mainnet at a specific block to recreate the vulnerable state.

## Adding a new shape

1. Author `<ShapeName>.t.sol.template` modeled on ReentrancyDrain's
2. Verify it compiles with `forge build` against a known target
3. Verify it FAILS the invariant on the buggy version and PASSES on the fixed version (the rule of two — Joe Spillner)
4. Update `tools/tlc_to_forge.py` SHAPE_TEMPLATES map
5. Update this README's status table

## Usage

```bash
# Translate one detection finding to a Foundry test
python tools/tlc_to_forge.py \
    --shape ReentrancyDrain \
    --target-path src/PuppyRaffle.sol \
    --target-contract PuppyRaffle \
    --target-fn refund \
    --target-fn-args "uint256 playerIndex" \
    --target-fn-call-args "0" \
    --out test/PoC_ReentrancyDrain.t.sol

# Then in the target's Foundry project:
forge test --match-test test_ReentrancyDrain_exploit -vvvv
```

## Status (verified 2026-06-08)

- Translator emits valid Solidity ✓
- ReentrancyDrain template + emitted test ran via `forge test` ✓
- Exploit reproduced on examples/puppy-raffle (drains 3 ETH via 2 re-entries) ✓
- Matches TLC counterexample from docs/tla/ReentrancyDrain.tla ✓

The setUp() block of the emitted file STILL needs target-specific
completion by hand (constructor args, initial state setup, attacker
registration). The translator emits a SKELETON. v2 of the template
system may include shape-specific setUp helpers; v1.1 is the verified
working baseline.

The other 8 shapes follow the same architecture: write a template, fix
the unicode/pragma issues, verify via forge test on a known target,
update this README's status row.
