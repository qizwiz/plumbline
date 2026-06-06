Calibration-drill goal: JH-vs-model head-to-head on a cold corpus.

Use when JH has 1-3 hours to cold-audit, OR after a contest is over
to grade plumbline's performance against ground truth. <4000 chars.

---

For one cold corpus (examples/<target>/), produce a measured diff
between JH's cold-read findings and what plumbline surfaces, so the
verifier-router (ADR-006) has grounded routing labels.

DONE WHEN ALL EIGHT HOLD:

1. examples/<target>/MY_FINDINGS.md exists, authored by JH (not the
   model). My transcript shows I read it. .ANSWERS.md is NOT
   referenced before scoring — only after.

2. examples/<target>/leads-plumbline.txt exists. My transcript
   shows `python sol_intent.py examples/<target> --recall` exit 0
   and the lead count.

3. For each of the 5 TLA+ FailureMode shapes, my transcript shows
   a retrieval query against the lead set and the top-3 matches.

4. Where retrieval hit a structural match with cos ≥ 0.55, my
   transcript shows a TLC run on the matched spec, with either
   `Invariant ... violated` (real bug) or `Model checking
   completed. No error has been found` (no match).

5. sol_score has run on both:
   - python sol_score.py MY_FINDINGS.md .ANSWERS.md → JH recall
   - python sol_score.py leads-plumbline.txt .ANSWERS.md → model recall
   Both numbers print to stdout.

6. examples/<target>/CALIBRATION.md exists, with these explicit
   rows (one per published finding in .ANSWERS.md):
   | finding | JH caught? | model caught? | mechanically discharged? |
   No "maybe" cells — yes/no only.

7. examples/<target>/CALIBRATION.md also contains per-finding labels
   for the verifier-router schema:
   - verifier_route: which verifier(s) WOULD have caught it
   - verifier_outcome: actual outcome on this corpus
   These are append-only candidates for reps.jsonl per ADR-006.

8. git log --oneline -3 shows ≥1 commit touching examples/<target>/
   (the CALIBRATION.md + the rep additions), and `git push origin
   main` completed successfully.

CONSTRAINTS:

- JH writes MY_FINDINGS.md cold. I do NOT see it before he commits.
- I do NOT open .ANSWERS.md until step 5 (after both finding-sets
  exist independently).
- Honesty over score: if the model finds something JH missed AND
  there's no mechanical discharge, label it "speculative" not "found."
  Speculative-not-confirmed is NOT a model win.
- "Verifier would have caught" labels are what we'd EXPECT given the
  shape, not what actually ran. Note the distinction.
- No prompt rewriting based on this drill mid-session. Lessons go
  in HYPOTHESES.md for between-contest review.

OUT OF SCOPE:

- Re-training the classifier on these new labels (separate session).
- Improving the prompt based on this corpus (between-contest only).
- Authoring new FailureMode specs (use CORPUS_GROWTH.goal.md).

If <target> .ANSWERS.md is missing (truly novel, unpublished
contest), stop at step 5: the diff can't be measured without ground
truth. Surface this; the drill is meaningless without it.
