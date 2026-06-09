## Pipeline Audit Report

### Headline numbers
- Tools inventoried: **36**
- TLA+ shapes: **14**
- DAG edges: **59**
- Simple pipelines enumerated: **36**
- Longest CLAIMED pipeline: **8 stages**
- Longest VERIFIED pipeline: **8 stages** (with caveats — see below)
- Reality ratio: **8/8 = 1.0 on stage count**, but only **3 of 5 sampled pipelines** are FULLY_WORKS end-to-end → effective reality ratio **0.60**

### Every pipeline (table)
| # | Pipeline | Stages | Verdict | Breakage |
|---|----------|--------|---------|----------|
| 1 | c4_ingest → build_findings_index → rag_query → structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm → render_report | 8 | FULLY_WORKS | None (terminates at static report) |
| 2 | c4_ingest → build_findings_index → rag_query → structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm → contest_day | 8 | FULLY_WORKS | contest_day is a dead-end node (no downstream consumer) |
| 3 | c4_ingest → build_findings_index → rag_query → structural_cascade → sol_intent_cascade → oracle_loop → tlc_oracle_loop → tlc_to_forge | 8 | FULLY_WORKS (stages execute) | **tlc_to_forge** emits only 1 of 9 shape templates (ReentrancyDrain), never confirmed to compile under `forge test` — terminal stage is vapor |
| 4 | manual_rep → build_findings_index → rag_query → structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm → render_report | 8 | PARTIAL_WORKS | manual_rep bypasses C4 ingest — coverage claim depends on operator hand-staging |
| 5 | validate_tla_grammar → spec_retrieval → rag_query → structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm → render_report | 8 | FULLY_WORKS | None at stage level; BuggyAction noise still pollutes weak_confirm input |

### Longest VERIFIED pipeline (the answer to JH's question)
**8 stages, pipeline #1**:
`c4_ingest → build_findings_index → rag_query → structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm → render_report`

What it actually delivers: a markdown report containing CONFIRMED findings filtered through weak_confirm's vocabulary-anchor STRONG/WEAK gate. Real value-add at each stage is verified by the run logs.

**Caveats the run logs do not advertise:**
- tlc_oracle_loop's CONFIRMED count is **~76 raw, mostly noise** (per weak_confirm's own docstring) — only **the post-weak_confirm STRONG bucket** is signal.
- render_report is a terminal leaf — no closed loop to contest_day, no downstream scoring against Sherlock truth.
- The "8 stages" includes ingest+index+query plumbing; the **novel research contribution is concentrated in stages 4–7** (cascade → sol_intent → tlc_oracle → weak_confirm). Stages 1–3 and 8 are RAG boilerplate and Jinja rendering.

So: **8 stages run, but the load-bearing surface is 4 stages wide.** Pipelines #3 and #4 reach 8 nominal stages but break at the terminal node.

### Vapor / orphan / dead-end list

**Vapor (claims unsupported by code):**
- `nca_train` — explicit "NOT BUILT YET" in own docstring; depends on `tools/synth_bugs.py` also stubbed. **Pure architectural placeholder.** Also the sole orphan node.
- `tlc_to_forge` — 1/9 shape templates emitted, never run under `forge test`. Marketed as "universal 2026 submission standard"; reality is one unverified Solidity stub.
- `autonomous_loop` — "11 cycles, $3.90" is a spend wrapper; status_guess concedes no DONE-by-loop verdicts. **Tracks money, not closure.**
- `cfg_decode` — own docstring admits constrained decoding does NOT fix v1 noise problem; BuggyAction fires regardless. **Syntactic win, semantic null.**
- `tlc_oracle_loop`'s raw CONFIRMED label — vacuous without weak_confirm. **The oracle's primary output is noise by its own admission.**
- `calibrate_against_sherlock` — conditional on gitignored PDFs and unverified pdftotext install. **Works only when operator has manually staged everything.**

**Orphans (1):** `nca_train` — no inbound edges, no outbound consumers.

**Dead ends (11):** `shape_evolve`, `score_against_sherlock_truth`, `tlc_to_forge`, `contest_day`, `fitness_card`, `autonomous_loop`, `validate_reps`, `dedup_reps`, `replay`, `render_report`, `gauntlet`. Eleven terminal leaves means **31% of the graph is sink nodes** — much of the inventory is end-of-line tooling with no feedback into upstream improvement.

### Top 3 plumbline gaps to close next

1. **Close the TLC noise loop: BuggyAction parameterization.** weak_confirm exists *only* because tlc_oracle_loop's CONFIRMEDs are mostly noise. Fix the spec so BuggyAction fires conditional on cfg_generator params, and weak_confirm becomes a sanity check instead of the actual filter. Scope: 1–2 TLA+ specs + cfg-generator wiring. Effort: **2–4 days**.

2. **Make tlc_to_forge real for ≥3 shape templates and run `forge test` against a known C4 winner.** Right now the "TLC → executable PoC" claim hangs on one unverified Solidity file. Pick 3 of the 9 shapes (Reentrancy, AccessControl, ArithmeticOverflow are highest-EV), template them, run forge against a public C4 finding, log the trace. Scope: 3 Jinja templates + forge harness + 1 fixture. Effort: **3–5 days**.

3. **Wire `score_against_sherlock_truth` (or `calibrate_against_sherlock`) into the loop as a precision/recall signal, not a dead-end leaf.** Without grounded scoring against real audit truth, render_report's STRONG bucket is unfalsifiable. Install pdftotext, stage the 259 Sherlock PDFs once, run the scorer, and feed precision back to weak_confirm thresholds. Scope: install + ingest + scoring harness + threshold loop. Effort: **2–3 days for v1**.

### Recommendation for JH

**Real today**: the 4-stage research surface — structural_cascade → sol_intent_cascade → tlc_oracle_loop → weak_confirm — is the only load-bearing innovation, and it works end-to-end on C4 input down to a markdown report. That is the asset. The 8-stage "longest pipeline" framing is technically true but misleading: stages 1–3 are RAG plumbing anyone can replicate, and stage 8 is Jinja. **Worth building**: close the BuggyAction noise loop (gap #1) so the oracle's raw output is meaningful without a vocabulary post-filter — that is the highest-leverage single fix because it converts weak_confirm from "the filter that makes the system honest" into "a redundant sanity check," which is the right altitude for a contest tool. Also build tlc_to_forge for real on 3 shapes (gap #2) — without an executable PoC, the contest-day claim is unfalsifiable. **Scrap or quarantine**: nca_train (vapor, orphaned), autonomous_loop (spend tracker masquerading as closure), and the contest_day/fitness_card/gauntlet/replay leaves until there is a feedback edge from them back into the cascade. Eleven dead-end nodes in a 36-node graph is a signal you have been building leaves instead of closing loops — that matches your own "Strongly Connected Components" rule, and the audit confirms you are violating it.