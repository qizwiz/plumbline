{{retrieved_findings}}

Below are similar bugs from past audits. Use as inspiration; the target corpus may have ENTIRELY different bug shapes. Don't pattern-match too literally — the SHAPE of the bug matters, not the exact identifiers.

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
