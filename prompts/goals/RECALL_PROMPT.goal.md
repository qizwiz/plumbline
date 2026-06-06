Between-contest goal: improve prompts/sol_find.md to surface the
specific mechanisms sol_intent missed on sequence (chained-mode bypass,
batch-binding, cross-wallet replay). Measure improvement via A/B.
~$5. <4000 chars; 8-step. EXPLICITLY between-contest only.

---

For corpus examples/sequence (where sol_intent --recall scored 0.0
strict-judge recall), edit prompts/sol_find.md to add lens-specific
guidance for the missed mechanisms, then re-run + score to measure
improvement.

DONE WHEN ALL EIGHT HOLD:

1. prompts/sol_find.md.bak exists (backup of pre-edit version).

2. prompts/sol_find.md has been edited to ADD (not replace) lens-
   specific guidance for at least these three mechanisms, derived from
   sol_score's "MISSED" output in examples/sequence/sol-intent-leads.txt:
   - flag-bypasses-validation-chain (H-01 shape)
   - per-element-guard-without-batch-binding (H-02 shape — note this
     was the new TLA+ FailureMode authored 2026-06-06)
   - cross-wallet-sig-replay via missing EIP-712 domain (M-01 shape)
   `git diff prompts/sol_find.md` shows the additions inline.

3. Re-run: examples/sequence/sol-intent-leads-v2.txt exists from
   `python sol_intent.py examples/sequence --recall` after the edit.

4. sol_score on the new run prints recall + precision. Cumulative
   spend tracked.

5. examples/sequence/RECALL_AB.md exists comparing:
   `before: recall=0.0  after: recall=0.NNN  delta=+0.NNN`
   `before: precision=0.0  after: precision=0.NNN`
   `missed-mechanisms-still-missing: <list>`

6. If recall delta is POSITIVE: commit the prompt edit + comparison
   artifact + log rep with proposer.kind="model" version="recall-v2".
   If recall delta is ZERO or NEGATIVE: revert prompts/sol_find.md to
   .bak version, log the failed iteration in
   prompts/sol_find_iteration_log.md with explanation, and surface to
   JH before declaring done.

7. reps.jsonl gained one row reflecting the v2 score (manual_rep or
   model_rep, whichever applies).

8. `git push origin main` succeeded; cloud loop on head SHA completed
   green within ~10 min.

CONSTRAINTS:

- This goal IS the explicit exception to constraint 4.3 (no mid-contest
  prompt rewrites). It is BETWEEN-CONTEST work, deliberately so.
- One iteration per session — do NOT chain v2 → v3 → v4 in the same
  goal; that's how prompt thrash happens. If v2 fails, revert and try
  different additions in a new session.
- $20 ceiling. Surface BEFORE the second re-run if it would exceed.
- The .bak file is the rollback. Do not delete it until v2 is merged.

OPERATING DISCIPLINE:

- The PRINCIPLE is: surfacing the mechanism class without surfacing the
  specific bug location is still valuable — the recall judge is strict
  but the discharge pipeline only needs the right structural lens.
- Lens-specific guidance > pattern-pile. Add structural-pattern
  paragraphs, not more "look for things like X" lists.
- Self-critique at step 6: "did the prompt change recall on this
  corpus, or did it just look like it should?"

OUT OF SCOPE:

- Improving other prompts (sol_intent.md, etc) — separate goal.
- Ensemble across multiple prompt versions — that's ENSEMBLE.goal.md.
- Re-running on corpora other than sequence — focus the iteration.

If v2 recall is ZERO again, the structural patterns in the prompt
aren't reaching the model's attention. Surface for JH review — may
need a different prompt-engineering approach (constrained decoding,
retrieval-augmented prompting, etc.) outside this goal's scope.
