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
    implementation fails a promise it makes. Do NOT assume correctness because it compiles or because the
    docstring sounds right — check the mechanism. Prioritize files the struggle map flags.

For each violation, give: **location** (contract::function), **promise_broken**, **mechanism** (concrete —
include the decimals/rounding math or the attack ordering), **exploit_sketch**, **severity**
(high/medium/low), **fix** (one line). A finding only counts if it's a real divergence from a stated
promise — not a style nit.

Return markdown:
## Intent — the promises
## Violations — where the code betrays them   (struggle-prioritized; highest severity first)

=== GROUNDED LESSONS (bug patterns you have demonstrably MISSED before — derived from measured recall, not
opinion; weight these heavily, they are your known blind spots) ===
{{lessons}}

=== STRUGGLE MAP (git history: where they fought bugs) ===
{{struggle}}

=== README ===
{{readme}}

=== ADRs ===
{{adrs}}

=== SOLIDITY SOURCE ===
{{sources}}
