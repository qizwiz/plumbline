# tlc_to_forge — PoC templates

One Foundry-test template per FailureMode shape. The translator
`tools/tlc_to_forge.py` selects the matching template, substitutes
target contract path + function name + parameters from the TLC
counterexample, and emits a runnable `.t.sol` file.

## Status

| shape | template | status |
|---|---|---|
| ReentrancyDrain | `ReentrancyDrain.t.sol.template` | v1 written, **unverified** — needs `forge test` run |
| SignatureReplay | — | TODO |
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

## Status caveat (commit b7049d9 + this commit)

This whole subsystem is **v1 unverified** as of commit-time. The Python
emits Solidity; the Solidity has not yet been compiled + run against a
real target. The morning's first task is to drop the emitted file into
the puppy-raffle Foundry project and verify `forge test` reproduces
the published H-1 exploit. Until then, treat all output as "structurally
correct, but semantics need ground-truth verification on a known bug."
