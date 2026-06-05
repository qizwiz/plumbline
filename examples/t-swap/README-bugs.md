# t-swap — bug index

Cross-reference of `.ANSWERS.md` findings to specific line ranges in
`TSwapPool.sol` / `PoolFactory.sol` (pragma `0.8.20`). One row = one finding.

| ID   | Title                                                                                 | File                | Line range          | Mechanism (one-liner) |
| ---- | ------------------------------------------------------------------------------------- | ------------------- | ------------------- | --------------------- |
| H-1  | `deposit` missing deadline check — transactions complete after the deadline           | `TSwapPool.sol`     | 113 (deposit decl); cf. 73 modifier `revertIfDeadlinePassed` | the `deposit` function signature takes `deadline` but the function body does not apply `revertIfDeadlinePassed(deadline)` |
| H-2  | Incorrect fee in `getInputAmountBasedOnOutput` — protocol takes too many tokens       | `TSwapPool.sol`     | 282–296             | `* 10000 / ... * 997` should mirror a 0.3% fee (`/ ... * 997` on output side); the literal 10000 is the wrong scale, so inputs are over-charged |
| H-3  | Lack of slippage protection in `swapExactOutput` — users can get way fewer tokens     | `TSwapPool.sol`     | 337–360             | `swapExactOutput` accepts an `outputAmount` but does not require a `maxInputAmount`, so price slippage can push input arbitrarily high |
| H-4  | `sellPoolTokens` mismatches input/output tokens — wrong amount returned to user       | `TSwapPool.sol`     | 365–375             | `sellPoolTokens(amount)` calls `swapExactOutput(..., poolToken, weth, amount, ...)` passing `amount` as the desired OUTPUT, but the user intended `amount` as INPUT |
| H-5  | Extra tokens given every `swapCount` breaks `x * y = k`                              | `TSwapPool.sol`     | 47 (`SWAP_COUNT_MAX`); 399–403 (`_swap` bonus) | every 10th swap, `_swap` transfers an unaccounted 1e18 of `outputToken` to the caller, dropping `reserveIn * reserveOut` below the prior `k` |
| L-1  | `LiquidityAdded` event parameters out of order                                        | `TSwapPool.sol`     | 52 (event decl); 196 (emit) | indexed/positional fields don't align with NatSpec; consumers reading the event get the wrong values |
| L-2  | Default return of `swapExactInput` results in incorrect return value                  | `TSwapPool.sol`     | 298–334             | the function declares a named return `outputAmount` but never assigns; defaults to 0, callers see "swap returned 0" |
| I-1  | `PoolFactory__PoolDoesNotExist` is unused and should be removed                       | `PoolFactory.sol`   | 22                  | declared error never reverted |
| I-2  | Lacking zero address checks                                                           | `PoolFactory.sol` + ctor of `TSwapPool` | n/a (various) | constructors / setters accept `address(0)` for token addresses |
| I-3  | `PoolFactory::createPool` should use `.symbol()` instead of `.name()`                 | `PoolFactory.sol`   | 47–60               | LP-token naming derives from `.name()` (verbose, non-conventional); convention is `.symbol()` |
| I-4  | Event missing `indexed` fields                                                        | `TSwapPool.sol`     | 52 (`LiquidityAdded` decl) | indexers/UI lose efficient filtering capability |

## How to use this index

When `sol_intent` (or any other proposer) emits a finding, eyeball the cited
line range against the row above. If `sol_intent` cites the right line but
phrases the mechanism wrong, that's a *labeling* problem (Layer 1 scorer
should still match via identifier overlap). If it cites the wrong line
entirely, that's a *finding* problem and the proposer missed.

This index is curated, not generated. If `TSwapPool.sol` / `PoolFactory.sol`
are edited, the line ranges drift and someone needs to update them.
