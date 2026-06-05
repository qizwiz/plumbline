You are recovering BUILDER INTENT for a smart-contract security audit. You are given the human record a
team left behind — README, ADRs (architecture decision records), and Solidity source with NatSpec — plus
a "struggle map" from their git history (files with many fixes/reverts = where they fought bugs, so look
there hardest). Software is a human artifact: a bug is the GAP between what the builders *meant* and what
they *made*. Find that gap.

Do two things:

(1) INTENT — reconstruct the concrete invariants/guarantees the builders PROMISE the protocol upholds.
    Confidence order: ADRs (highest — explicit recorded decisions) > NatSpec docstrings > README. Write
    each promise as a single checkable statement (e.g. "redeem(mint(x)) returns exactly x").

(2) VIOLATIONS — find every place the CODE SILENTLY CONTRADICTS its own stated intent: where the
    implementation fails a promise it makes. **CRITICAL THRESHOLD: Only report a violation if you have a COMPLETE MECHANISTIC PROOF tracing the exploit through ACTUAL code with REAL values showing the EXACT numerical divergence from the promise.**

**Mandatory evidence for EVERY violation you report:**

1. **EXACT CODE LOCATION**: contract::function at line X where the breaking operation occurs
2. **QUOTED PROMISE**: The verbatim text from ADR/NatSpec/README that this violates
3. **COMPLETE MECHANICAL PROOF**: Trace through the ACTUAL Solidity code with SPECIFIC variable names and arithmetic:
   - Start state: `totalSupply = 1000e18, reserves = 1000e6, userBalance = 0`
   - Step 1: User calls `mint(100e18)` 
   - Line 42: `shares = amount * totalSupply / reserves` → `100e18 * 1000e18 / 1000e6 = 100e30`
   - Line 43: `balances[user] += shares` → `userBalance = 100e30`
   - Line 44: `totalSupply += shares` → `totalSupply = 1100e30`
   - Step 2: User immediately calls `redeem(100e30)`
   - Line 58: `payout = shares * reserves / totalSupply` → `100e30 * 1000e6 / 1100e30 = 90.9e18`
   - **DIVERGENCE**: Promise guarantees `redeem(mint(x)) = x` but `90.9e18 ≠ 100e18` (9.1% loss)
4. **EXPLOIT PROOF-OF-CONCEPT**: Executable instructions with concrete inputs/outputs:
   ```
   1. Deploy contract with 1000e6 USDC reserves, 1000e18 shares supply
   2. Alice calls mint(100e18) → receives 100e30 shares (line 42-44)
   3. Alice calls redeem(100e30) → receives 90.9e18 USDC (line 58)
   4. Measured loss: 9.1e18 USDC (9.1%) contradicts "exact round-trip" promise
   ```

**BEFORE declaring a violation, you MUST verify ALL of these:**

- [ ] You can quote the EXACT promise text (not inferred, not "obvious" — actually written)
- [ ] You have traced through the ACTUAL Solidity code paths (not pseudocode, not "this would happen")
- [ ] You have calculated SPECIFIC NUMERIC VALUES showing the promise breaks (not "could break," but "breaks by X amount")
- [ ] The numeric divergence CATEGORICALLY contradicts the promise (if promise says "approximately" and you find 0.0001% error, that is NOT a violation; if promise says "exactly" and you find 9% error, that IS)
- [ ] You can write reproduction steps that would compile and run (not theoretical, not "an attacker might")

**REJECT these as findings:**

- Any violation you cannot trace line-by-line through the actual code with real variable names
- Rounding differences that fall within implicit tolerance (≤0.01% when promise uses approximate language; if promise says "exact" then even 1 wei matters)
- Access control concerns UNLESS you can prove they break an explicit written promise about who can do what
- "This enables..." or "An attacker could..." unless you demonstrate the EXACT attack with numbers showing promise-break
- Reentrancy/MEV/slippage risks UNLESS (a) the docs promise protection AND (b) you show the numeric exploit
- Breaking unstated "best practices" — only stated promises matter
- Violations you can only describe with words like: "potential," "possible," "might," "could," "may," "allows," "enables"

**Precision check**: Before submitting each violation, re-read the promise. Does your numeric proof show CATEGORICAL contradiction, or minor deviation? If the promise says "backed 1:1" and your trace shows 0.999999:1 due to rounding in one operation that doesn't compound, that is NOT a violation. If your trace shows 0.9:1 because reserves can be drained, that IS. When in doubt about whether numeric divergence contradicts the promise, EXCLUDE the finding — err toward precision.

**Recall discipline**: Extract ALL promises from the documentation. For each promise, attempt to find a violation. If you cannot construct a complete mechanistic proof with numbers, explicitly write "No mechanistic violation found for Promise X" in your violations section — do not silently skip.

**Struggle-map prioritization**: Scrutinize struggle-map files with extra care (they debugged there for a reason), but apply IDENTICAL proof standards — a file's history does not lower the bar for evidence.

For each violation output: **location** (contract::function:line), **promise_broken** (exact quote), **mechanism** (line-by-line state trace with calculated values), **exploit_poc** (numbered reproduction steps), **severity** (high/medium/low based on promise criticality and numeric impact), **fix** (one-line code remedy).

Return markdown:
## Intent — the promises
## Violations — where the code betrays them   (struggle-prioritized; highest severity first)

=== STRUGGLE MAP (git history: where they fought bugs) ===
{{struggle}}

=== README ===
{{readme}}

=== ADRs ===
{{adrs}}

=== SOLIDITY SOURCE ===
{{sources}}