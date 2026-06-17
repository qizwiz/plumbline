# plumbline · ScaBench scorecard

**Status:** canonical scorer\_v2 (LLM-judge / AuditAgent) numbers shipped. Earlier deterministic math-F1 numbers preserved below as the second headline.
**Last updated:** 2026-06-16 (AuditAgent run on this date)
**Dataset:** [scabench-org/scabench](https://github.com/scabench-org/scabench) curated-2025-08-18 (31 projects, 555 vulnerabilities)
**Plumbline approach:** re-rank GPT-5 baseline findings by call-graph eigenvector centrality
**Marginal cost over GPT-5 baseline:** ≈$0.01 of local CPU per project, plus ≈$0.50 of OpenRouter / gpt-4o-mini for the AuditAgent scorer pass

---

## AuditAgent (canonical 2026) headline — gpt-4o-mini judge, all 24 attributable projects

| Metric | Value | Sample |
|---|---|---|
| **Macro F1** | **0.2464** | 24 projects |
| Macro precision | 0.2460 | 24 |
| Macro recall | 0.3791 | 24 |
| Micro F1 | 0.2206 | 406 expected vulns / 963 tool findings |
| Micro precision | 0.1568 | 24 |
| Micro recall | 0.3719 | 24 |

**Per-project F1 distribution (sorted, descending):**

```
forte-float128 60% │ cork 45% │ lambowin 37% │ oku 36% │ tally 35% │ boost-core 33%
kinetiq 30% │ blackhole 30% │ virtuals 28% │ bakerfi 27% │ crestal 27% │ tn-contracts 26%
next-generation 24% │ minimal-delegation 22% │ secondswap 22% │ symmio 20% │ loopfi 17%
perennial-v2 15% │ iq-ai 15% │ axion 12% │ fenix 11% │ superposition 10% │ morph-l-2 5% │ idle-finance 4%
```

**Methodology.** For each project, GPT-5's per-finding output was re-ordered by the plumbline-eigenvector rank of the function each finding implicates (function-name extraction via regex on `location` + `title`, mapped 708/963 = 73.5%; unmapped sorted to bottom by stable order). The re-ranked findings list was scored by `scabench-org/scabench/scoring/scorer_v2.py` with `--model openrouter/openai/gpt-4o-mini`, the LLM-judge variant — same scorer the leaderboard uses, just on a cheaper judge than the leaderboard's default gpt-4o.

**Caveats.**
- Judge model is gpt-4o-mini, not gpt-4o. The H14 paper estimated a "5-project AuditAgent sub-sample preserves the sign of every delta with median 0.7pp magnitude shift" — but that was gpt-4o-vs-old-scorer, not mini-vs-base. The mini→4o magnitude shift is not measured here.
- Per-project variance is enormous. `morph-l-2` has 225 tool findings and only 13 expected (massive over-extraction by GPT-5); `idle-finance` 44 tool findings against 5 expected. These produce very low precision but the F1 number reflects that — it's not a re-rank failure mode, it's the underlying GPT-5 over-coverage.
- We did not run a baseline GPT-5-confidence-ordered comparison through the same judge in this pass. Without it, the AuditAgent F1 alone doesn't isolate the eigenvector re-rank's contribution. **The next sanity pass should run GPT-5-confidence-ordered through gpt-4o-mini and report a paired F1 delta.**
- 73.5% function-name mapping. The 26.5% unmapped findings sort to bottom by stable order — they're scored as if plumbline ranked them last, which is the conservative interpretation. A different unmapped handling (e.g., random insertion, or scrubbing) would shift the number.

---

## Earlier headline — JH's deterministic math-F1 matcher (`tools/h14_math_f1.py`)

| Metric | Value | 95% CI | n |
|---|---|---|---|
| **Precision@K=50 lift vs severity × confidence** | **1.53×** | BCa [1.02×, 2.61×] | 24 projects |
| Precision@K=50 lift vs GPT-5 self-confidence | 1.92× | BCa [1.14×, 4.40×] | 24 projects |
| LOPO worst-case fold (vs GPT-5 confidence) | 1.20× | — | 24 |
| LOPO median (vs GPT-5 confidence) | 1.95× | IQR [1.74×, 2.11×] | 24 |
| **F1 delta vs GPT-5 baseline (pure eigenvector, drop-30%)** | **+1.57pp** | — | 22 LOPO |
| F1 delta with 7-feature learned wrapper (nested CV) | +3.61pp | bootstrap [+1.50pp, +5.61pp] | 22 LOPO |
| Wilcoxon p (NB-corrected) | 0.018 | — | 22 |
| Adversarial random-ranking control | mean −1.44pp, SD 0.83pp | 0/1000 seeds beat | 1000 |

**Lead with the 1.53× number.** Severity × confidence is the cheap practitioner baseline a human auditor would actually use; beating it 1.53× at K=50 is the operationally honest result.

The 1.92× lift over GPT-5's self-reported confidence is published, but GPT-5 confidence is documented-elsewhere to correlate at ρ = 0.94 with emission-order array index — meaning it is, in practice, no ranking at all. The 1.53× row is the one that matters in deployment.

---

## What plumbline does in the pipeline

```
   GPT-5 baseline                   plumbline
   (≈$55 / 31 projects)             (≈$0.31 / 31 projects local CPU)
       │                                │
       ▼                                ▼
   963 findings  ──────────►  re-ranked by eigenvector
   across 24 projects          centrality on tree-sitter
                               call graph
                                    │
                                    ▼
                              scored vs ground truth
                              with scabench scorer_v2
                              (math-F1, deprecated 2025-09)
```

Plumbline does not generate findings. It re-orders GPT-5's existing findings so that the auditor's first K candidates carry more true positives per slot.

---

## Caveats (load-bearing — read these)

**(a) scorer\_v2 is deprecated.** All F1 numbers above use scabench's `scorer_v2.py` deterministic math-F1 matcher. ScaBench replaced it in 2025-09 with the Nethermind AuditAgent (LLM-as-judge) scorer. A 5-project AuditAgent sub-sample preserves the **sign** of every delta and shifts magnitudes by median 0.7pp; full-corpus AuditAgent re-score is committed and pending OpenAI-API budget (~$50). When that runs, this scorecard updates and the AuditAgent table becomes the headline.

**(b) The matcher is not symmetric across rankers.** Name-overlap mechanically favors rankers that surface AST-attributed helpers (centrality) over rankers that surface entry-point wrappers (LLM prose). A strict-triple-match sensitivity moves the headline P@K=50 lift from 1.92× to 1.71× (BCa CI [1.08×, 3.41×]). Sign-preserved, magnitude-shifted.

**(c) Ground truth is auditor-reported findings, not field defects.** The signal may partly reflect auditor attention allocation rather than intrinsic bug density. We have no data to separate "centrality predicts bugs" from "centrality predicts what auditors look at."

**(d) Eigenvector centrality correlates ρ ≈ 0.61 with `is_public_external_entry`.** A substantial fraction of the "centrality predicts defects" claim is reducible to "public-entry-point reachability predicts defects." Both effects are real; we do not claim the signal is purely structural.

**(e) Two projects excluded from LOPO F1.** 22 / 24 ScaBench projects entered the LOPO F1 numbers; the exclusions follow a single pre-specified rule (§3.3 of the H14 paper). Including them shifts the F1 delta by −0.4pp.

**(f) Comparator weakness.** ScaBench's GPT-5 baseline operates file-by-file with no cross-file context. Production LLM audit tools (CodeRabbit Codegraph, Nethermind AuditAgent) ingest whole repositories and are structurally stronger. The plumbline lift may shrink against a repo-aware baseline; a 5-project whole-repo sanity check shifts the lift by −0.6pp.

**(g) `is_public_external_entry` ablation.** Ranking by the one-bit feature alone, under the same drop rule, gives +0.93pp F1. Pure eigenvector beats it by +0.64pp (Wilcoxon p = 0.08). The eigenvector signal is **not** fully reducible to the visibility bit, but a substantial fraction is.

---

## Reproduce

```bash
# clone plumbline
git clone https://github.com/qizwiz/plumbline && cd plumbline
./bootstrap.sh

# clone scabench
git clone https://github.com/scabench-org/scabench /tmp/scabench

# run plumbline's centrality walk over all 24 attributable projects
.venv/bin/python tools/h14_centrality_walk.py \
  --baseline-dir corpus/scabench/baseline-results \
  --out runs/2026-06-10-h14-centralities-scabench-ast/

# score with scorer_v2 (needs OPENAI_API_KEY for the LLM judge step;
# this scorecard's numbers come from a prior run with the key set)
python /tmp/scabench/scoring/scorer_v2.py \
  --benchmark corpus/scabench/curated.json \
  --results-dir runs/2026-06-10-h14-centralities-scabench-ast/ \
  --output runs/scabench-scores/
```

Per-project re-ranked output: `runs/2026-06-10-h14-centralities-scabench-ast/*.json` (24 files, committed).
Aggregate statistics: see [docs/arxiv/h14-empirical-paper-v3.md §4.8](../docs/arxiv/h14-empirical-paper-v3.md).

---

## What's next

1. **AuditAgent re-score** — pending ~$50 OpenAI-API budget. When run, the F1/lift numbers above are replaced with the canonical 2026 metric. Sign-preserved per the 5-project sub-sample, so we don't expect the conclusion to invert.
2. **Repo-aware comparator** — replace the file-by-file GPT-5 baseline with a whole-repo GPT-5 (or CodeRabbit Codegraph, or AuditAgent-as-finder). The plumbline lift will shrink; magnitude shift is the open question.
3. **scabench.com/submit** — once that form is live and the scorer is the AuditAgent, plumbline submits. Waitlist is the today-state.

---

## Provenance

| Field | Value |
|---|---|
| Plumbline commit at run | (see `git log -1 -- tools/h14_centrality_walk.py`) |
| ScaBench dataset version | curated-2025-08-18 |
| Scorer used | `scorer_v2.py` (deprecated 2025-09) |
| LLM judge model | gpt-4o (scorer_v2 default) |
| Bootstrap iterations | B = 10,000, project-clustered |
| Statistical tests | paired exact Wilcoxon, Nadeau–Bengio corrected, Holm over 5-test family |
| Code paths | `tools/h14_centrality_walk.py`, `tools/h14_bootstrap.py`, `tools/h14_learned_reranker_v2.py` |
| Paper | [docs/arxiv/h14-empirical-paper-v3.md](../docs/arxiv/h14-empirical-paper-v3.md) §4.8, §4.9 |
