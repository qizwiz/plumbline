# Manifest Registry — Universal PoC Template Inputs

Each `<target>-<shape>.json` in this directory is a per-target, per-shape
description that `tools/trace_to_forge.py` fills into
`templates/foundry_poc/_universal.t.sol.template` to produce a runnable
Foundry test.

## Verified manifests

| Manifest | Shape | Target | Pragma | Verdict |
|---|---|---|---|---|
| `puppy-raffle-ReentrancyDrain.json` | ReentrancyDrain | PuppyRaffle | ^0.7.6 | forge PASS |
| `dre-PausedDistributorPricingAsymmetry.json` | PausedDistributorPricingAsymmetry | dreUSDs | 0.8.28 | forge PASS |

Run all: `python3 tools/manifest_lint.py --run`

## Schema

```jsonc
{
  "shape": "<ShapeName>",                  // must match docs/tla/<ShapeName>.tla
  "forge_root": "examples/foo",            // relative to plumbline root (REQUIRED for --run)
  "tla_spec_path": "docs/tla/Shape.tla",
  "invariant": "InvariantName",
  "target": {
    "path": "src/Contract.sol",            // relative to forge_root
    "contract": "Contract",
    "target_fn": "vulnerableFn",           // for the trace-header comment
    "pragma": "^0.8.20"
  },
  "state_vars":            [ "Foo public x;", "..."  ],
  "attacker_contract":     { /* optional, see template */ } | null,
  "setup_block":           [ "// runs inside setUp()", "..." ],
  "trace_replay_block":    [ "// runs inside test_<Shape>_invariantViolated", "..." ],
  "invariant_assert_block":[ "assertTrue(...);", "..." ],
  "tlc_trace_head":        [ "State 0: ...", "State 1: ..." ],
  "extra_imports":         [ "import {Foo} from '...'" ]   // optional
}
```

## Footguns (each one cost real session time once)

### vm.prank consumption (DRE M-1 session, ~30 min)

`vm.prank(X)` pranks ONLY the next external call. If the next statement contains
an inner call inside its argument list, the prank is consumed by the inner call
and the outer call runs from the test contract:

```solidity
// BUG: vm.prank consumed by victim.balanceOf
vm.prank(alice);
uint256 r = victim.redeem(victim.balanceOf(alice), alice, alice);
//                        ^^^^^^^^^^^^^^^^^^^^^^^ consumes the prank
```

Symptom: `ERC20InsufficientAllowance(testContract, 0, amount)` — looks like
an allowance bug, is actually prank consumption.

**Fix patterns:**

```solidity
// Pattern A: cache the inner call
uint256 bal = victim.balanceOf(alice);
vm.prank(alice);
uint256 r = victim.redeem(bal, alice, alice);

// Pattern B: vm.startPrank / vm.stopPrank for multi-call blocks
vm.startPrank(alice);
asset.approve(address(vault), type(uint256).max);
vault.deposit(50 ether, alice);
vm.stopPrank();
```

The same applies to setup_blocks. Always use `startPrank/stopPrank` for any
multi-call user action.

`tools/manifest_lint.py` flags this pattern with a WARN.

### Pragma mismatch (puppy-raffle, ~10 min)

Set `target.pragma` to MATCH the target contract's pragma. `^0.8.20` will
not compile a 0.7.6 target. The universal template uses `target.pragma`
verbatim in its `pragma solidity` line.

### Missing extra_imports (DRE M-1)

If your test references types beyond the default `Test` + `target.contract`,
list them in `extra_imports`. They're inserted verbatim before the test
contract. Same applies to inline `contract MockToken is ERC20 {...}`
helper contracts — declare them in `extra_imports` (no need for a separate file).

### forge_root resolution

Always set `forge_root` explicitly. The fallback heuristic walks
`corpus/calibration/` and `examples/` looking for a `foundry.toml` whose
project contains `target.path` — slow and not always correct.

## Authoring a new manifest

1. Pick a shape from `docs/tla/`. Note the invariant name.
2. Pick a target codebase. Note `forge_root`, `target.path`, `target.contract`,
   `target.pragma`.
3. Sketch the setup block in a scratch file. Run forge there; iterate until it compiles + you can deposit/initialize all roles.
4. Sketch the trace replay block. **Use `startPrank`/`stopPrank`** when in doubt.
5. Sketch the invariant assert block. Should match what TLA+ INVARIANT says.
6. Sketch a 6-state TLC trace head as comments (`tlc_trace_head`).
7. List any extra imports in `extra_imports`.
8. Save as `tools/manifests/<target>-<shape>.json`.
9. Run `python3 tools/manifest_lint.py --manifest <path> --run`.
10. Iterate manifest only — never edit the emitted .t.sol directly.

## Known-broken targets

- `examples/boss-bridge` — OZ snapshot is incomplete (no `MessageHashUtils`, broken `lib/openzeppelin-contracts/test/.../ERC4626.t.sol` references). Manifest authoring deferred until env is repaired.
