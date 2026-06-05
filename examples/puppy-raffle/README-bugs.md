# puppy-raffle — bug index

Cross-reference of `.ANSWERS.md` findings to specific line ranges in
`PuppyRaffle.sol` (pragma `^0.7.6`). One row = one finding.

| ID   | Title                                                                                | Line range          | Mechanism (one-liner) |
| ---- | ------------------------------------------------------------------------------------ | ------------------- | --------------------- |
| H-1  | Reentrancy in `refund` lets attacker drain contract                                  | 96–105              | external `sendValue` at line 101 BEFORE state write `players[playerIndex] = address(0)` at line 103 (CEI violation) |
| H-2  | Weak randomness in `selectWinner` lets anyone choose winner                          | 125–155 (esp. 129)  | `keccak256(msg.sender, block.timestamp, block.difficulty)` — all inputs miner/sender-influenced |
| H-3  | Integer overflow of `totalFees` loses fees                                           | 30; 134; 158        | `uint64 totalFees` (line 30) accumulates via `uint64(fee)` cast (line 134); exceeds 2^64-1 ≈ 18.4 ETH and wraps |
| H-4  | Malicious winner can forever halt the raffle                                         | 145–155             | `_safeMint`/payout to a contract that reverts in `receive` or lacks `onERC721Received` blocks reset of state |
| M-1  | `enterRaffle` O(n²) duplicate-check loop is a DoS vector                             | 79–92 (esp. 86–90)  | nested for-loop over `players` grows quadratically in players count |
| M-2  | `withdrawFees` strict-equality balance check enables selfdestruct grief              | 157–161 (esp. 158)  | `require(address(this).balance == uint256(totalFees))` can be broken by forced ETH (selfdestruct) |
| M-3  | Unsafe cast of `fee` loses fees                                                      | 134                 | `uint64(fee)` truncates per-raffle fees exceeding 2^64-1 wei |
| M-4  | Smart-contract winners without `receive`/`fallback` halt prize transfer              | 145–155 (sendValue) | ETH payout reverts when winner is a contract without ETH-receive — related to H-4 |
| I-1  | Floating pragma                                                                      | 2                   | `pragma solidity ^0.7.6;` should be pinned |
| I-2  | Magic numbers                                                                        | 131–133             | `* 80 / 100`, `* 20 / 100` should be named constants |
| I-3  | Test coverage                                                                        | n/a                 | code-coverage gap (project-wide) |
| I-4  | Zero-address validation                                                              | 60–62 (constructor) | `feeAddress` set without `address(0)` check; brick fees if zero |
| I-5  | `_isActivePlayer` is unused dead code                                                | 173–181             | internal helper never called |
| I-6  | Unchanged variables should be `constant` or `immutable`                              | various             | e.g. URIs, raffle duration |
| I-7  | Potentially erroneous active player index                                            | 110–117             | `getActivePlayerIndex` returns `0` for "not found", colliding with the legitimate index `0` |
| I-8  | Zero address may be erroneously considered an active player                          | 96–105; 110–117     | `address(0)` sentinel after refund overlaps with un-set entries — related to I-7 |

## How to use this index

When `sol_intent` (or any other proposer) emits a finding, eyeball the cited
line range against the row above. If `sol_intent` cites the right line but
phrases the mechanism wrong, that's a *labeling* problem (Layer 1 scorer
should still match via identifier overlap). If it cites the wrong line
entirely, that's a *finding* problem and the proposer missed.

This index is curated, not generated. If `PuppyRaffle.sol` is edited, the
line ranges drift and someone needs to update them.
