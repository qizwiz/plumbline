Paste into `/goal` at the start of a contest session. <4000 chars.
Built per code.claude.com/docs/en/goal: measurable end state +
stated check + constraints. Decomposed to ≤8 self-progressing steps
to fit the documented 8-block Stop-hook cap. Every check is something
my own transcript output will demonstrate (TLC/halmos/slither stdout,
git diff, file paths).

---

For the active contest scope at examples/<contest>/, drive plumbline
end-to-end so every submitted finding cites a mechanically-discharged
artifact, and the per-contest corpus growth lands on main.

DONE WHEN ALL EIGHT HOLD:

1. examples/<contest>/scope-read.md exists; my last bash output shows
   I read the contest README + scope.md before any tool runs.

2. examples/<contest>/slither.txt exists; tail shows slither exit 0
   and a finding count.

3. examples/<contest>/leads.txt exists with ≥1 lead per ANSWERS
   high-severity finding (cross-checked via grep against the
   contest's .ANSWERS.md when available; if no .ANSWERS.md, lead
   count ≥ source LOC / 200 as a recall floor).

4. For every lead my last transcript turn marked as candidate, ONE
   of these holds and is printed in the transcript:
   - "TLC: Invariant <name> is violated" + counterexample
   - "halmos: 0 counterexamples" or "halmos: COUNTEREXAMPLE FOUND"
   - "slither: <detector> at <file>:<line>" matching this lead
   - explicit "human_only: <reason>" with a 1-sentence justification

5. examples/<contest>/triage-skipped.md lists every dropped candidate
   with a 1-line reason (one of: time, low-prob, no-corroboration,
   dup, scope).

6. examples/<contest>/SUBMITTED.md lists each submission with
   (severity, mechanism, mechanical citation). Every row has a
   citation; no row is "model said so."

7. git log --oneline -5 shows ≥1 commit touching reps.jsonl AND ≥1
   commit touching docs/tla/ (the corpus must grow this contest).

8. git push output shows main is up to date with origin; the cloud
   loop's last gh run completed successfully on the head SHA.

CONSTRAINTS THAT MUST HOLD ACROSS ALL TURNS:

- AI proposes; verifier disposes. No finding leaves with only LLM
  prose backing. If I cannot mechanically discharge, the finding
  is labeled "human_only" and surfaced for JH before submission.
- reps.jsonl is APPEND-ONLY. Never rewrite past rows.
- No autonomous prompt rewrites this contest (between-contest only).
- Every LLM run logs $ spent to stdout. If cumulative > $20 in this
  session, stop and surface to JH before continuing.
- `forge build` is always run with `--ast` before any halmos call.
- If TLC OOMs on a candidate, record it as "needs larger bound" in
  triage-skipped.md; do NOT silently drop.
- If the cloud loop is dead (gh run list shows red on last 3),
  surface BEFORE retrying — don't loop on a dead pipeline.
- "human_only" is a legitimate terminal state, not failure. Surface
  it explicitly; never auto-resolve to a guess.

OPERATING DISCIPLINE (compounding the corpus):

- For each VERIFIED finding that matches NONE of the 5 existing
  FailureMode shapes in docs/tla/, draft a new TLA+ FailureMode
  + .cfg, run TLC to confirm the bug-shape, and commit to
  docs/tla/. This is how each contest grows the next.
- Hypothesis tree: maintain examples/<contest>/HYPOTHESES.md listing
  candidate bug-classes considered, confidence (low/med/high),
  evidence path attempted, verdict. Per Anthropic's research-shape
  best practice.
- Self-critique at step 5: before promoting a candidate, ask "what
  did I miss?" Add the answer to HYPOTHESES.md.

OUT OF SCOPE THIS CONTEST:

- CA / NCA work over Solidity grammar lattice (future, not this run).
- Constrained-decoding wire-up (T8 still pending; current substrate
  uses retrieval + TLC).
- Online prompt rewriting (between-contest only).
- Calibration drill (T9 deferred per JH constraint).

If <contest> directory doesn't exist, stop and surface — the goal is
contest-scoped; without a target nothing else makes sense.
