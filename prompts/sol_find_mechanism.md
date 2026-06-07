{{retrieved_evidence}}

Below are two sources of inspiration — confirmed past audit findings AND matched bug-class shapes from a TLA+ FailureMode library. Use BOTH. The shape descriptions name structural patterns; the findings show how those shapes appeared in real code. Target corpus may have entirely different bugs; pattern-match the STRUCTURE not the identifiers.

## MECHANISM-GROUNDED FORMAT (required)

For EVERY finding you list, use this format:
```
- function_or_module FILE:LINE — SPECIFIC variables (e.g., msg.sender, the storage slot uint96 timestamp, the function param userOp.sender) — the SPECIFIC transformation (e.g., "msg.sender becomes EntryPoint during EntryPoint.handleOps forwarding, while userOp.sender stays the actual submitter") — one sentence on why this is exploitable.
```

DO NOT write findings as bug-class categories. Write them as mechanism specifications:

WRONG (too generic): "[ACCESS CONTROL] validateUserOp — may have wrong authorization"
RIGHT (mechanism-grounded): "validateUserOp() in ERC4337v07.sol:42 — checks msg.sender == ENTRY_POINT_ADDR (an immutable) against the live msg.sender — but during EntryPoint.handleOps forwarding msg.sender IS the EntryPoint contract, not the user-op's actual submitter (userOp.sender) — so the check passes for any user-op submitted through EntryPoint regardless of the configured signer."

The mechanism format makes the downstream verifier (TLA+ shape match) cleanly hit. Bug-class lists confuse it.

You are doing a RECALL-FIRST audit pass on Solidity source. List EVERY plausible vulnerability or
intent-violation you can find. ERR TOWARD INCLUSION — a separate downstream pass filters for precision, so
a credible concern is worth listing even without a full proof. Do NOT self-censor; do NOT demand certainty.
Breadth beats caution here.

Walk the code through EACH of these lenses explicitly and list what you find under each — do not skip a
lens even if you think it's clean (say "none found" only after actually checking):

1. ACCESS CONTROL & INIT — unprotected initializers, missing modifiers, first-caller/owner takeover,
   role/registry pointers an owner can rebind, privileged setters without validation.
2. ORACLE / PRICE FEED — staleness, price-deviation, TWAP manipulation/ordering, missing sequencer/L2
   uptime check, unit/decimals mismatch in price math.
3. ARITHMETIC — narrowing casts / truncation (uintN(x)), rounding DIRECTION (favoring user), unchecked
   divisors (division by a value that can be 0), overflow inside `unchecked` blocks, asymmetric rounding.
4. TOKEN ACCOUNTING — unchecked ERC20 transfer/approve return, allowance zero-first, fee-on-transfer
   assumptions, balanceOf-as-amount, getPoolTokens/exitPool output assumptions, full-balance burns.
5. ARRAY / INDEX / INPUT VALIDATION — out-of-bounds indexing, totalSupply()-bounds assumptions, ERC721
   id==0 edge, missing zero/range checks on inputs.
6. EXTERNAL CALLS & REENTRANCY — CEI violations, unchecked low-level .call, reentrancy ordering, untrusted
   callback/post-transfer assumptions.
7. CROSS-CHAIN / BRIDGE — decimals scaling omission, message/chain-id truncation, recipient-field confusion,
   freeze/sanctions/pause inconsistency across flows, paused-state inversion.
8. ECONOMIC / INCENTIVE LOGIC — reward vesting reset/dust, epoch getter sparse-init / off-by-one,
   donation/inflation, slippage (hard-coded minOut), positional-token assumptions in swaps/burns.

For EACH issue: **location** (Contract::function), **issue** (one line), **why-it-could-break** (one line).
List liberally — many short bullets, not few long proofs.

Return markdown:
## Findings
- [lens] Contract::function — issue — why it could break

=== STRUGGLE MAP ===
{{struggle}}
=== README ===
{{readme}}
=== ADRs ===
{{adrs}}
=== SOLIDITY SOURCE ===
{{sources}}
