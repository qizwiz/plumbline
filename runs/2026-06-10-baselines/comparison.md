# Slither vs Plumbline: head-to-head on Cyfrin training corpora

**REVISED 2026-06-09 EVENING** — initial comparison claimed plumbline beat Slither 5.6× on recall. JH challenged the number; re-running `sol_match.py` fresh against the existing `examples/<corpus>/slither.txt` files showed the cached `slither-recall.txt` files were from an older inconsistent scorer. The corrected numbers below are more modest and honest.

## Methodology

- Slither output: existing `examples/<corpus>/slither.txt` (Slither v0.x, exact version not pinned)
- Plumbline output: per-corpus reps in `reps.jsonl` (sol_intent proposer)
- Both scored by **current** `sol_match.py` against the same `examples/<corpus>/.ANSWERS.md` ground truth
- Match rule: deterministic identifier overlap OR embedding cosine ≥ 0.80

## Corrected results

| Corpus | Slither R | Slither P | Plumbline R (mean) | Plumbline P (mean) | N reps |
|---|---|---|---|---|---|
| t-swap | 1.00 (11/11) | 0.03 (186 leads) | 0.89 | 0.51 | 11 |
| boss-bridge | 0.86 (6/7) | 0.01 (291 leads) | 0.82 | 0.34 | 11 |
| thunder-loan | 0.86 (6/7) | 0.01 (308 leads) | 0.78 | 0.31 | 11 |
| sequence | 0.25 (3/12) | 0.002 (1375 leads) | 0.54 | 0.31 | 20 |
| puppy-raffle | 0.20 (3/15) | 0.02 (49 leads) | — | — | 0 |

**Aggregate (4 corpora with reps):** Slither R=0.74, plumbline R=0.76 — *comparable*.

## Honest interpretation

1. **Slither and plumbline achieve comparable recall** on these benchmarks. The earlier 5.6× claim was based on stale cached scores; reality is much closer.

2. **Slither's apparent low precision is largely a measurement artifact.** `sol_match` tokenizes line-by-line; Slither's multi-line findings (header + external calls + event references + URLs) explode into 49–1375 "leads" per corpus. With Slither-specific tokenization (one finding per `Detector:` block), precision would be much higher.

3. **Differential coverage is real and is the actual story.** Slither catches structural patterns (reentrancy, access control, arithmetic). Plumbline catches logic invariants (deadlines, fee math, slippage, conservation). On `sequence` (logic-heavy), plumbline R=0.54 vs Slither R=0.25 — likely real. On `t-swap` (structural-pattern-heavy), Slither R=1.00 vs plumbline R=0.89 — Slither's pattern library wins.

4. **The right framing is composition, not replacement.** This supports H1 (dimension stacking) — Slither at the structural-pattern layer, plumbline at the logic-invariant layer, halmos at the symbolic-discharge layer. The paper should claim composition advantage, not standalone superiority.

5. **N=4 corpora is small.** `c4_ingest.py` has ~1191 ingested Code4rena findings available; a follow-up paper should run this at scale with proper per-tool tokenization.

6. **Puppy-raffle is missing from plumbline's measurements** — needs a fresh rep before the comparison there is meaningful.

## What's defensible to claim in the arXiv paper

✗ "Plumbline beats Slither 5.6× on recall." **FALSE — do not claim.**

✓ "Slither and plumbline achieve comparable recall on Cyfrin training benchmarks (mean ~0.75 each across 4 corpora)."

✓ "The tools have differential coverage — Slither dominates on structural patterns (R=1.00 on t-swap), plumbline dominates on logic-invariant bugs (R=0.54 on sequence vs 0.25)."

✓ "Apparent precision differences are largely tokenization artifacts; both tools merit careful per-output-format scoring."

✓ "These results support H1 (composition of verifier-discharged structural pipelines) rather than tool replacement."
