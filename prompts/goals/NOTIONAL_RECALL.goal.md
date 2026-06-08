Notional-Exponent real recall — convert the 93.7% RAG corpus ceiling
into a measured detection number on a known-ground-truth contest.

This is the smallest experiment that tells us how much of the corpus
ceiling sol_intent + RAG actually captures. The cost-benefit is the
sharpest of any pending experiment: ~$10 LLM spend, one contest,
one number.

---

DONE WHEN ALL SEVEN HOLD:

1. corpus/calibration/notional-source/ exists (re-clone if needed from
   github.com/sherlock-audit/2025-06-notional-exponent). Already gitignored.
   Scope: notional-v4/src/*.sol (54 files).

2. python tools/sol_intent.py corpus/calibration/notional-source/notional-v4/src
   --hybrid-rag --output corpus/calibration/notional-leads.jsonl
   exits 0. Transcript shows the lead count.

3. Each lead in notional-leads.jsonl has the standard plumbline shape
   (contract path, function, evidence, top-3 retrieved priors).

4. A scoring script (existing tools/sol_score.py if it takes jsonl,
   else write a 30-LOC scorer at tools/score_against_sherlock_truth.py)
   compares notional-leads.jsonl against
   corpus/calibration/notional-ground-truth.jsonl (37 H+M findings).

5. Three numbers print:
   - recall@all: fraction of ground-truth findings with ANY plumbline
     lead that names the same contract+function or thematically matches
   - precision: fraction of plumbline leads that map to a real finding
   - severity-correct-recall: fraction of real findings detected with
     correct severity tier

6. corpus/calibration/CALIBRATION_NOTIONAL_RECALL.md exists, including:
   - Three numbers from step 5
   - Per-finding table: ground-truth id, ground-truth title, plumbline
     hit Y/N, severity match Y/N, lead text (truncated)
   - Honest scope: what was matched mechanically vs thematically
   - Estimated cost of the run from tools/autonomous_spend.json delta

7. git log shows ≥1 commit touching corpus/calibration/ + tools/, and
   `git push` completed.

CONSTRAINTS:

- Hard cost cap: $15 from autonomous_spend.json. If sol_intent looks
  like it will exceed, halt and write what was produced + estimated
  marginal cost to complete.
- Matching is THEMATIC plus mechanical: a plumbline lead "counts" as
  catching a ground-truth finding if either (a) it names the same
  contract+function, or (b) its retrieved top-3 priors include a finding
  with title cos>0.85 to the ground-truth title.
- The thematic-match rule is generous — it counts the corpus knowing
  the bug class, not necessarily localizing to the right line. Report
  both numbers (mechanical-only and mechanical+thematic).
- Sol_intent uses Anthropic SDK via tools/llm.py — must use existing
  cost tracking (autonomous_spend.json delta = actual recorded cost).

OUT OF SCOPE:

- TLC discharge on the Notional contract (separate experiment).
- Generating Foundry tests for any found bug (separate experiment).
- Cross-contract whole-protocol analysis.
- Improving sol_intent prompt mid-run based on what we see.
- Running on a second contest (single calibration first; expand if
  the number is interesting).

WHY THIS GOAL EXISTS:

CALIBRATION_SHERLOCK_SWEEP measured the corpus at 93.7% coverage on real
Sherlock judgments. Sol_intent cold recall is 0.42 on examples/sequence
(self-graded). This goal measures sol_intent cold recall on Notional
(externally-graded). The delta between corpus ceiling and detection
reality tells us how much of plumbline's gap is in the retrieval+
grounding layer vs the corpus itself.

If the number is >70% recall, the structural cascade goal becomes lower
priority (sol_intent is already capturing most of the ceiling). If <30%,
the cascade is essential. The number routes the next month of work.
