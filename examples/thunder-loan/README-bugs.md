# thunder-loan — bug index

Cross-reference of `.ANSWERS.md` findings to specific line ranges across
`ThunderLoan.sol` / `ThunderLoanUpgraded.sol` / `AssetToken.sol` /
`OracleUpgradeable.sol` (pragma `0.8.20`). One row = one finding.

| ID   | Title                                                                                          | File                              | Line range                  | Mechanism (one-liner) |
| ---- | ---------------------------------------------------------------------------------------------- | --------------------------------- | --------------------------- | --------------------- |
| H-1  | Storage collision in upgrade — `s_flashLoanFee` lands at wrong slot post-upgrade               | `protocol/ThunderLoan.sol` 97–98; `upgradedProtocol/ThunderLoanUpgraded.sol` 97–98 | the slot order changes: `ThunderLoan` has `s_feePrecision` then `s_flashLoanFee` at slots N, N+1; `ThunderLoanUpgraded` has `s_flashLoanFee` then a `constant FEE_PRECISION` (no slot), so after upgrade `s_flashLoanFee` is read from the old `s_feePrecision` slot |
| H-2  | Unnecessary `updateExchangeRate` in `deposit` breaks withdraw and reward distribution          | `protocol/ThunderLoan.sol`        | 148–164 (`deposit`); 80 (`AssetToken::updateExchangeRate`) | `deposit` calls `assetToken.updateExchangeRate(calculatedFee)` even though `deposit` is not a flashloan event, inflating exchange rate and stranding withdrawer funds |
| H-3  | Stealing all funds by calling `deposit` instead of `repay` after flashloan                     | `protocol/ThunderLoan.sol`        | 181–229 (`flashloan`); 231–237 (`repay`); 148 (`deposit`) | `flashloan` checks the loan was repaid via `s_currentlyFlashLoaning[token]` and the AssetToken balance; `deposit` also increases the balance and bypasses the `repay` semantics — attacker mints AssetTokens for free |
| H-4  | `getPriceOfOnePoolTokenInWeth` uses TSwap price without decimal accounting                     | `protocol/OracleUpgradeable.sol`  | 19–26                       | `getPriceInWeth(token)` is called assuming 18-decimal input; mixed-decimal pools (e.g. USDC=6) feed in a 1e6-scale that gets divided by `s_feePrecision = 1e18` → fee misvaluation |
| M-1  | Centralization risk for trusted owners                                                         | `protocol/ThunderLoan.sol`        | 239 (`setAllowedToken`); 261 (`_authorizeUpgrade`) | owner can disable any token (DoS) or push a malicious upgrade |
| M-2  | TSwap-as-oracle enables price manipulation                                                     | `protocol/OracleUpgradeable.sol` + flashloan callsite | 19–26 (oracle); 260 (consumer) | TSwap reserves can be moved within a single flashloan tx → fee evaluated at manipulated price |
| M-4  | Fee-on-transfer / rebase tokens break accounting                                               | `protocol/ThunderLoan.sol`        | 148–164 (`deposit`); 231–237 (`repay`) | `deposit`/`repay` rely on exact ERC20 amount math; fee-on-transfer tokens deliver less than requested |
| L-1  | Empty function body — `_authorizeUpgrade` lacks a comment of intent                            | `protocol/ThunderLoan.sol`        | 261                         | empty body for an upgrade-authorization hook is permissive-by-default; readers can't tell if this is intentional |
| L-2  | Initializers can be front-run                                                                  | `protocol/ThunderLoan.sol`        | 140 (`initialize`); `protocol/OracleUpgradeable.sol` 11 (`__Oracle_init`) | `initializer` modifier protects against re-init, but the first call is a public race |
| L-3  | Missing critical event emissions when `s_flashLoanFee` changes                                 | `protocol/ThunderLoan.sol`        | `updateFlashLoanFee` (cf. upgrade 265–270) | no `event FlashLoanFeeUpdated(uint256 newFee)` emitted; off-chain observers miss fee changes |
| I-1  | Poor test coverage                                                                             | n/a                               | n/a                         | project-wide; especially `flashloan`, `_authorizeUpgrade`, oracle |
| I-2  | Not using `uint256[50] __gap` for future storage-collision mitigation                          | `protocol/ThunderLoan.sol`        | tail of storage              | upgradeable contracts conventionally append `uint256[50] __gap` to reserve room for new vars |
| I-3  | Different decimals may cause confusion (`AssetToken` 18dp vs underlying asset 6dp)             | `protocol/AssetToken.sol`         | constructor / decimals      | mixing 18-dp asset tokens with 6-dp underlying like USDC creates fee/exchange-rate math hazards (related to H-4) |
| I-4  | Doesn't follow EIP-3156                                                                        | `protocol/ThunderLoan.sol`        | 181–229 (`flashloan`)        | flashloan callback signature/semantics deviate from EIP-3156 — third-party borrowers can't integrate without adapters |

## How to use this index

Same shape as `puppy-raffle/README-bugs.md` and `t-swap/README-bugs.md`. When
`sol_intent` (or any proposer) emits a finding, eyeball the cited line range
against the row above. Right-line / wrong-mechanism = labeling problem.
Wrong-line = the proposer missed.

H-1 is the storage-collision class noted in the cron audit trail as
*outside halmos's scope* — see TODO.md `[skip:]` annotation. The right
verifier for that one is `forge inspect storage` or
slither-check-upgradeability, not symbolic EVM.

Curated, not generated. If the contracts shift, this index drifts.
