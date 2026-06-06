Between-contest goal: measure sol_intent recall variance via 3-run
ensemble on one corpus, derive union-of-leads recall, log ensemble rep.
Implements T11. Cost ~$15. <4000 chars; 8-step.

---

For ONE corpus (default: examples/sequence), measure sol_intent recall
variance across 3 cold runs, compute union-of-leads recall, and log a
named "ensemble" rep so plumbline has measured variance bands before
contest day.

DONE WHEN ALL EIGHT HOLD:

1. examples/<corpus>/sol-intent-run1.txt, run2.txt, run3.txt all exist;
   `wc -l` on each shows >20 leads.

2. examples/<corpus>/per-run-recall.txt exists, one line per run, format:
   `run1: recall=0.NNN precision=0.NNN n_leads=NN`. Computed via sol_score
   against .ANSWERS.md.

3. examples/<corpus>/union-leads.txt exists: deduped union across all 3
   runs (sort -u after normalizing). `wc -l union` > each individual run.

4. examples/<corpus>/ensemble-recall.txt exists with three numbers:
   `union recall: 0.NNN`, `union precision: 0.NNN`, `dispersion:
   max_run - min_run = 0.NNN`. Computed via sol_score on the union file.

5. examples/<corpus>/ENSEMBLE.md exists summarizing: per-run recall +
   precision table, union recall, dispersion, comparison to historical
   single-run reps in reps.jsonl.

6. reps.jsonl gained one row with proposer.kind="ensemble" via
   `python tools/manual_rep.py examples/<corpus> --findings ENSEMBLE.md`
   (or hand-append if manual_rep doesn't support the override — see
   ADR-006 schema notes).

7. Cumulative LLM spend printed to stdout, surfaced before each run.
   Stop if cumulative >$20 in this session.

8. `git push origin main` succeeded; cloud loop run on head SHA
   completed green within ~10 min.

CONSTRAINTS:

- $20 ceiling per goal contract — surface BEFORE the 4th run if needed.
- reps.jsonl is append-only.
- Use SAME corpus across all 3 runs (no mid-run scope change).
- Use SAME prompt across all 3 runs (no mid-run prompt change — that's
  the next goal, RECALL_PROMPT.goal.md).
- Each run uses fresh seed/temperature (the variance IS the signal).
- Honest reporting: if recall variance is high, that's the result —
  don't average-away the dispersion.

OPERATING DISCIPLINE:

- Run them sequentially, not in parallel — observe each result before
  the next so cost-spike fail-fast.
- After run 1, check cost; project 3x. If projection exceeds ceiling
  surface, do not auto-proceed.
- The union recall is the headline number: "ensemble surfaces N% of
  ground truth across 3 tries." Single-run recall is the calibration
  baseline.

OUT OF SCOPE THIS GOAL:

- Prompt improvement (RECALL_PROMPT.goal.md).
- Verifier-router retraining (ROUTER_TRAIN.goal.md).
- New TLA+ shapes (CORPUS_GROWTH.goal.md).

If projected cost > $20 mid-run, stop and surface — the variance
signal from 2 runs is still useful, and 3-run cost discipline matters.
