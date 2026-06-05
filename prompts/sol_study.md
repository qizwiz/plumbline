You are preparing an auditor for a SECURITY CONTEST on a protocol that has ALREADY been audited by
professional firms. You are given those prior audit reports (and any docs). The contest's value is
finding what the prior audits MISSED — so your job is to digest the priors into a CONTEST HUNT BRIEF
that maps the terrain. Be concrete and specific to THIS protocol; do not pad or generalize.

Produce exactly these sections:

## 1. Architecture
The components, the money-flow, and the key mechanisms — reconstructed from the audits' descriptions.

## 2. Findings catalog
Every finding: id · title · severity · status (Fixed / Acknowledged / Mitigated) · one-line mechanism.
Group by component. Flag the **Acknowledged / unfixed** ones explicitly — they're still in the code.

## 3. The team's recurring blind spots
The bug PATTERNS that appear more than once across the two audits. These recur in new/changed code.

## 4. CONTEST HUNT MAP  ← the point
A PRIORITIZED list of where to hunt, because the remaining bugs are almost always one of:
  (a) VARIANTS of fixed findings — same mechanism, a different code path (fixes are often incomplete);
  (b) ACKNOWLEDGED (unfixed) findings and their escalations;
  (c) areas the prior audits UNDER-scoped or marked out-of-scope;
  (d) INTERACTIONS between components that the single-feature findings didn't cover.
For each entry: the area · why it's hot (cite the prior finding it descends from) · the specific
invariant/condition to check · which plumbline harness (if any) fits.

Honesty: you cannot find the unfound bug from these reports — only map where it likely lives. Say so if
a section is thin.

=== PRIOR AUDITS + DOCS ===
{{material}}
