Between-contest goal: T15 — measure marginal recall per verifier
across the 5 example corpora (boss-bridge, puppy-raffle, sequence,
t-swap, thunder-loan). $0 (reuse existing reps where possible).
<4000 chars; 8-step.

---

For the 5 example corpora with .ANSWERS.md ground truth, measure:
(a) slither-alone recall, (b) sol_intent-alone recall (from existing
reps), (c) UNION (slither + sol_intent) recall — the marginal lift.
Tabulate per corpus + cross-corpus summary. This is the ADR-006
step 5 prerequisite + the CA/NCA baseline.

DONE WHEN ALL EIGHT HOLD:

1. examples/<corpus>/slither.txt exists for each of the 5 corpora.
   My transcript shows `ls examples/*/slither.txt` lists 5 files.

2. examples/<corpus>/slither-recall.txt exists for each, computed via
   `python sol_score.py slither.txt .ANSWERS.md`. One file per
   corpus, contains RECALL + PRECISION + n_leads.

3. examples/<corpus>/sol-intent-recall.txt exists for each, derived
   from the most-recent rep in reps.jsonl with proposer.kind=sol_intent
   for that corpus (no new LLM calls). Same format as #2.

4. T15_SUMMARY.md exists in project root with this table:

   | corpus | slither r/p | sol_intent r/p | union r/p | best alone |
   |--------|-------------|----------------|-----------|------------|
   ... 5 rows + a totals row.

5. T15_SUMMARY.md includes a paragraph answering: "If we had to pick
   ONE verifier for contest day, which?" — with the data backing it.

6. T15_SUMMARY.md includes a paragraph on dispersion across corpora.
   Per ENSEMBLE precedent: report min/max recall per verifier, NOT
   just averages. If slither recall varies 0.1 to 0.6 across corpora,
   that's the contest-day risk envelope.

7. git log --oneline -3 shows ≥1 commit landing T15_SUMMARY.md +
   the per-corpus slither/recall artifacts. `git push origin main`
   succeeded.

8. validate_reps.py still passes (no new rep writes required this
   goal — reading existing reps only).

CONSTRAINTS:

- $0 LLM spend. Slither is local. sol_intent results reused from
  existing reps.jsonl, NOT re-run.
- Don't run halmos/TLC — those need per-finding manual setup and
  are out of T15 scope (ADR-006 step 5 will revisit).
- reps.jsonl append-only — DON'T add new reps for derived recalls.
  Those go in *-recall.txt files alongside the slither outputs.
- If slither fails on a corpus (compiler version, dep issues),
  surface — record the failure in T15_SUMMARY.md instead of
  silently skipping.
- 5 corpora, ONE pass. No re-runs to improve numbers.

OPERATING DISCIPLINE:

- Per corpus order: boss-bridge → puppy-raffle → sequence (already
  has slither.txt) → t-swap → thunder-loan. Sequence first if a
  faster turn helps verify the pipeline.
- For each corpus: confirm the contract uses a solc version we have
  installed (0.8.27/0.8.28 already installed). If not, try
  solc-select install <ver> first — that's free.
- The HEADLINE NUMBER is the UNION recall per corpus. The
  surprise/insight is whether slither + sol_intent COMBINE useful
  signal or both miss the same bugs (in which case union ≈ max).
- Self-critique: "is the recall judge consistent across corpora,
  or does sol_score's strict-match break on some corpora's
  ANSWERS format?" Spot-check the matched/missed columns.

OUT OF SCOPE:

- New sol_intent runs (use existing reps).
- halmos / TLC per-finding marginal (separate goal).
- Improving prompts (RECALL_PROMPT.goal.md).
- Wiring this into route_lead_hybrid (between-contest, separate session).

If sol_intent reps don't exist for some corpora, surface — the
honest move is to report "no sol_intent rep for corpus X" in the
summary rather than spend LLM budget here. The $0 constraint stands.
