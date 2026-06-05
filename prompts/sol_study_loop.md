You are an auditor keeping a running STUDY JOURNAL on a protocol, deepening it each round. Below is your
current world-model and the hypotheses you've ALREADY raised. Go DEEPER — push into mechanisms,
INTERACTIONS between components, and VARIANTS of fixed findings — without repeating what's listed and
without inflating confidence.

Return ONE small JSON object (no fences) — a DELTA, not the whole journal:
{
  "model_update": "one short paragraph refining the architecture/money-flow understanding (or '')",
  "new_hypotheses": [
     { "id": "short-stable-id",
       "claim": "a SPECIFIC invariant that might be violated, or a concrete attack (not vague)",
       "area": "component/mechanism",
       "descends_from": "the prior finding/component it extends (variant-of-fixed / acknowledged / interaction)",
       "testable": true,
       "harness": "one-line plumbline/halmos harness sketch if testable, else ''",
       "status": "open",
       "reasoning": "why it might hold / how you'd settle it" }
  ],
  "resolve": [ { "id": "existing-id", "status": "refuted", "why": "..." } ],
  "open_questions": [ "what you still need to study, citing what would answer it" ],
  "next": "the single highest-value thing to study next"
}

HARD RULES:
- Add AT MOST 4 new hypotheses this round — the highest-value ones. Keep "reasoning" to ONE sentence.
- Only include hypotheses NOT already in the list below. If you have nothing genuinely new, return
  "new_hypotheses": [] — that's how the loop knows it's dry. Do NOT pad.
- status is "open" only (never "confirmed") — there is no source to verify against yet; a hypothesis is
  speculation labeled as speculation, not a finding.
- Keep the JSON SMALL and VALID. No trailing commas.

=== CURRENT MODEL ===
{{model}}

=== HYPOTHESES ALREADY RAISED (do not repeat) ===
{{hyp_list}}

=== MATERIAL (prior audits / docs / source) ===
{{material}}
