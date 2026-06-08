# Calibration: plumbline RAG corpus vs ALL Sherlock past audits

## Headline

**93.7% corpus coverage on Sherlock's full published audit archive.**

| Severity | Total findings | cos>0.7 prior | Coverage |
|---|---|---|---|
| High | 705 | 660 | **93.6%** |
| Medium | 1619 | 1518 | **93.8%** |
| **TOTAL** | **2324** | **2178** | **93.7%** |

## Method

Per `tools/calibrate_against_sherlock.py`:

1. List all 259 PDFs at github.com/sherlock-protocol/sherlock-reports/audits
2. For each: fetch → pdftotext → strip form-feed page-breaks → regex-parse `Issue [HM]-N: title` headings
3. For each finding title: embed via bge-small-en-v1.5 with identifier-lifting
4. Nearest-neighbor against plumbline's 1240-finding RAG index
5. cos>0.7 → "semantically reachable prior in corpus"

Sweep stats:
- 259 PDFs total in archive
- 223 had parseable H/M findings (86%)
- 33 skipped — 0 H+M (clean audits or different heading conventions)
- 3 skipped — fetch/extract failure

Per-finding distribution of nearest-neighbor cosine similarity:
- mean: **0.787**
- median: **0.784**
- p10: **0.712** (90% of findings have a prior at cos>0.71)
- p90: **0.865** (10% of findings have a prior at cos>0.87)

The cos>0.7 threshold is conservative; lowering to 0.65 would push coverage to ~97-98%.

## What this number IS

- **The first external validation of plumbline** against graded ground truth that plumbline did not produce itself.
- A measurement of corpus quality — does the 1240-finding RAG index contain semantic priors for real-world Sherlock-graded bugs?
- Answer: yes, broadly. 94% coverage at conservative threshold.

## What this number IS NOT

- **Detection recall.** This measures whether the corpus HAS a thematic prior, not whether sol_intent FINDS the bug in the source.
- **Precision.** Doesn't account for false positives from the same retrieval producing irrelevant matches.
- **Mechanical equivalence.** Matched priors are thematic, not always mechanism-matched (e.g., "cross-contract reentrancy" matches to "reentrancy if recipient is malicious" — same class, different code shape).
- **Generalization to Immunefi/Cantina/Spearbit.** Sherlock only. Different platforms have different bug-class distributions.

## Where the 6.3% gap is

146 findings with cos≤0.7. Lowest-similarity examples:

| sev | cos | title (often truncated by pdftotext) |
|---|---|---|
| H | 0.535 | "Fontaine never stops the flows" |
| H | 0.592 | "Nobody can buy" |
| M | 0.597 | "Incomplete Topic Processing" |
| M | 0.604 | "Nobody can cast for any proposal" |
| M | 0.621 | "In the Tranche.sol, there is no" |
| H | 0.623 | "Lister is overpaying during the" |

Two patterns in the gap:
1. **Truncated titles** — pdftotext sometimes cuts titles mid-word at column boundaries, leaving phrases with little semantic signal.
2. **Protocol-specific jargon** ("Tranche.sol", "FTokens", "Fontaine") — terms with no semantic neighborhood unless the surrounding context is provided.

The gap is largely a **measurement artifact**, not a real corpus shortcoming. If we used full finding *body* text instead of *title* text, coverage would likely be ≥97%.

## Strategic implication for plumbline

**The bottleneck is not the corpus.** The corpus already has ~94% ceiling on Sherlock H/M coverage. Continuing to grow the corpus (more c4 ingestion, Spearbit/TOB PDFs, etc.) has diminishing returns from here.

**The bottleneck is the detection pipeline** — translating "code-text → matched-prior" into "is THIS specific function buggy?" The 0.42 cold sol_intent recall on `examples/sequence` measured earlier suggests detection captures roughly **half of the ceiling**. The other half is lost between retrieval and grounded localization.

The right investment from here is structural composition (tree-sitter / AST queries + NetworkX call graphs + embedding NN + TLA+ shape match + halmos discharge as a cascade), not corpus expansion.

## Caveats worth flagging

1. **Sample is Sherlock-only.** Immunefi bug classes may differ (more protocol-integration edge cases).
2. **Embedder bias.** bge-small-en-v1.5 was not domain-tuned. A code-aware embedder might shift results in either direction.
3. **Ground truth includes duplicates.** Sherlock counts each judge-graded issue; some are dupes of the same root cause. Coverage % is on issue-count basis, not unique-bug basis.
4. **Format variation.** Older Sherlock reports use different finding heading formats (Cascade, some 2026 contests) and were skipped. The 33 skipped contests with 0 H+M parsed may have had real findings we missed.

## Files

- `corpus/calibration/sherlock_coverage.jsonl` — per-contest record with per-finding top-1 match + cos
- `corpus/calibration/notional-ground-truth.jsonl` — N=1 spot-check (Notional Exponent, July 2025)
- `corpus/calibration/CALIBRATION_NOTIONAL.md` — original single-contest writeup (this doc supersedes for aggregate claims)
- `tools/calibrate_against_sherlock.py` — repeatable sweep tool
