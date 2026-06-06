Between-contest goal: implement ADR-006 steps 1-4 of the verifier-
router (schema → relabel → multi-class trainer → inference CLI).
Validate against threshold. $0 LLM spend (all local). <4000 chars; 8-step.

---

Implement the verifier-router design from docs/adr/ADR-006-verifier-
router.md so plumbline can route leads to the cheapest sufficient
verifier (slither / halmos / TLC / human) before contest day. Train on
the historical reps.jsonl + new sequence rep.

DONE WHEN ALL EIGHT HOLD:

1. reps.jsonl schema migration: my last bash output shows
   `python tools/validate_reps.py` passes AFTER adding optional fields
   `verifier_route` and `verifier_outcome` to row schema (additive,
   never removing existing fields — append-only contract preserved).

2. tools/relabel_for_router.py exists, ~50 LOC max, applies the
   deterministic rules table from ADR-006 §"Label rules" to existing
   rows. My last bash output shows
   `python tools/relabel_for_router.py` reports `N rows routed,
   M rows ambiguous (need manual)`.

3. reps_routed.jsonl exists in the project root (NOT replacing
   reps.jsonl — the contract is append-only on the original; this is
   a derived view). `wc -l reps_routed.jsonl` >= 41.

4. tools/ml_zoo_router.py exists (fork of ml_zoo.py). My last
   `python tools/ml_zoo_router.py train` output shows: per-class
   precision + recall + f1 in a printed table, and saves
   tools/router_classifier.pkl.

5. tools/router_results.json exists with:
   - 5-fold CV top-1 accuracy
   - 5-fold CV top-2 accuracy
   - average cost (predicted verifier runs per lead)

6. ACCEPTANCE CRITERIA per ADR-006:
   - top-2 accuracy >= 0.85
   - avg cost <= 1.5
   Both numbers printed to stdout. If either fails, surface to JH
   with options (more labels, different model, schema revision)
   before declaring done.

7. tools/route_lead.py exists. My last bash output shows
   `echo "signature accepted twice no nonce" | python tools/route_lead.py`
   returns an ordered list of verifiers with probabilities, e.g.
   `tlc (0.72), slither (0.18), human (0.10)`.

8. `git push origin main` succeeded; cloud loop on head SHA completed
   green within ~10 min. git log shows ≥1 commit touching tools/
   and ≥1 touching reps_routed.jsonl.

CONSTRAINTS:

- $0 LLM spend — all sklearn/local.
- reps.jsonl is append-only (constraint 4.2 of contest goal). The
  routing labels live in reps_routed.jsonl, NOT in reps.jsonl rows.
- No retraining on the same row history twice (cross-validate, then
  retain). The classifier's training set is the rep log, full stop.
- If top-2 accuracy < 0.85: do NOT lower the bar. Either find more
  labels or revisit the label set. Honest failure > moved goalposts.
- ADR-006 step 5 (pipeline wire-up) is OUT of scope this goal — that
  waits on T15 marginal-recall data, per the ADR itself.

OPERATING DISCIPLINE:

- 5-fold STRATIFIED CV (some classes will be sparse — likely
  human_only and slither_will_catch).
- Save the model AND the feature pipeline (sklearn Pipeline).
  Inference at route-time must use the same featurizer.
- Multi-class is balanced via class_weight='balanced' (consistent
  with current ml_zoo).
- The router CLI must default to TOP-K=2 output (per ADR routing
  policy: try the top-2 in cost order).

OUT OF SCOPE:

- Pipeline wire-up to sol_intent → route_lead → verifier (T15+).
- Online learning during contest.
- Confidence calibration.
- Improving sol_intent recall (RECALL_PROMPT.goal.md).
- Adding new bug-class shapes to corpus (CORPUS_GROWTH.goal.md).

If reps.jsonl + sequence add up to fewer than 40 rows with non-null
verifier_route, the training set is too small for 4-class CV. Surface
and propose either: (a) collect more reps via dry-run substrate
validation on other corpora, OR (b) collapse to binary
{will-discharge, human_only} as a v0 router.
