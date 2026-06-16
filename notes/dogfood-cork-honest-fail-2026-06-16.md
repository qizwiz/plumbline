# Plumbline dogfood — cork-protocol honest fail, 2026-06-16

Ran plumbline against `sherlock_cork-protocol_2025_01` (18 known findings, curated in `corpus/scabench/curated.json`). The headline H-01 — "Lack of slippage protection" in `VaultLib.redeemEarly` at `cork/contracts/libraries/VaultLib.sol:639` — got ranked **82 of 87**. We would have missed it.

This note is what I'd tell Mariam if she asked "should I run this on Monday?"

## 1. The honest result

Plumbline's top 10 on cork, with a reader-of-Solidity's read:

| # | Function | Read |
|---|---|---|
| 1 | `ModuleState.getRouterCore` | noise — bare view getter |
| 2 | `ModuleState.getAmmRouter` | noise — view |
| 3 | `DummyWETH.deposit` | noise — dummy contract |
| 4 | `VaultCore.provideLiquidityWithFlashSwapFee` | plausible |
| 5 | `RouterState.__afterFlashswapBuy` | FP — `+erc20.unchecked` on protocol-owned tokens |
| 6 | `AssetFactory.getDeployedAssets` | noise — view |
| 7 | `VaultCore.depositLv` | plausible |
| 8 | `RouterState.swapDsforRa` | maybe — same protocol-token concern |
| 9 | `PsmCore.depositPsm` | plausible |
| 10 | `AssetFactory.deployLv` | plausible |

4 useful, 4 noise, 2 false positives. **Useful starter, not magical.**

H-01's triggering wrapper `VaultCore.redeemEarlyLv` lands at rank **82 of 87**. `VaultLib.redeemEarly` itself doesn't appear as a node at all.

## 2. What was missed, and why

The bug is in a library function, called through a `using VaultLibrary for State;` directive in `VaultCore`. The call chain is:

```
VaultCore.redeemEarlyLv  →  state.redeemEarly(...)
                                ↓  (Solidity `using` rewrite)
                            VaultLib.redeemEarly  →  _liquidateLpPartial
                                                   →  _redeemCtDsAndSellExcessCt
                                                   →  ammRouter.swapExactTokensForTokens(amt, 0, ..., block.timestamp)
```

`sol_graph` builds the call graph by **name-based resolution**. `state.redeemEarly(...)` looks like a method call on a struct — there's no syntactic edge to `VaultLib.redeemEarly`. The library function appears orphaned: zero in-degree, zero centrality, ranked at the bottom with the other unreached nodes. The wrapper `redeemEarlyLv` is reachable but shallow, so it lands near the bottom too.

This is a known limitation of name-based graphs on Solidity. We hit it on a contest where it matters.

## 3. What got surfaced anyway

The graph isn't worthless. `FlashSwapRouter` functions take **5 of the top 15** slots. Cork's two other high-severity findings are H-02 ("empty Reserve") and H-08 ("Attackers steal reserve"), both rooted in `FlashSwapRouter` logic around reserve accounting. Plumbline ranks these structurally important functions correctly — the topology *does* know FlashSwapRouter is load-bearing.

So: H-01 missed (library indirection), H-02 / H-08 plausibly catchable from the top-15 (FlashSwapRouter cluster). On 18 findings total, "we'd catch 2 of the 3 highs and miss the headline" is a calibrated, unflashy result.

## 4. Fixes, ranked by impact

**A — 15 min: dummy/test skip + view/pure deprioritization.** Filter `DummyWETH` and any contract under `test/` or `mocks/` out of the ranking. Demote functions where the AST shows `view` or `pure` and no state writes anywhere transitive. This alone removes 3 of the 4 noise items from the top 10 above.

**B — 2-3 hr: `using` directive resolution in `sol_graph`.** Parse `using X for Y;` declarations per contract and rewrite `expr.foo(...)` edges to `X.foo(expr, ...)` when `expr` has type `Y`. Requires the type information `tree-sitter-solidity` already has on identifier nodes. This is the one that catches H-01: once `VaultCore.redeemEarlyLv → VaultLib.redeemEarly` is an edge, `redeemEarly` inherits the centrality of its wrapper and the `_liquidateLpPartial / _redeemCtDsAndSellExcessCt` chain becomes reachable.

**C — this note.** So the next person who runs cork (or any contest with heavy library use) sees the failure shape before re-deriving it.

## 5. Mariam's calibrated read post-fix

Current state: ~40% useful in top 10.

After **A** alone: noise items drop out, plausible items move up. Useful-rate goes to **~65-70%**. Still misses H-01 — `using`-routed library bugs remain invisible.

After **A + B**: H-01's bug site (`VaultLib.redeemEarly`) becomes a reachable, central node. Plausibly top-20, possibly top-10 given the centrality it inherits from `VaultCore`. This is the move that catches the headline finding.

**A is the cheap unlock. B is the one that changes the verdict from "useful starter" to "I'd run this Monday."**

The science (Ricci on the call graph) isn't what failed here. The **graph construction** failed — we were ranking a graph that didn't contain the bug.
