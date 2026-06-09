# Slither vs Plumbline: head-to-head on Cyfrin training corpora

**Data source:** existing `examples/<corpus>/slither-recall.txt` files (Slither output already scored via sol_match) compared against per-corpus `reps.jsonl` entries (plumbline sol_intent output, same scorer).

**Result:** plumbline beats Slither by **5.6× on recall** and **3.2× on precision** across 4 benchmark corpora.

| Corpus | Slither P | Slither R | Plumbline P (mean) | Plumbline R (mean) | N reps |
|---|---|---|---|---|---|
| boss-bridge | 0.14 | 0.20 | 0.34 | 0.82 | 11 |
| sequence | 0.05 | 0.08 | 0.31 | 0.54 | 20 |
| t-swap | 0.18 | 0.18 | 0.51 | 0.89 | 11 |
| thunder-loan | 0.08 | 0.07 | 0.31 | 0.78 | 11 |
| **Mean** | **0.12** | **0.13** | **0.36** | **0.76** | — |

## Honest caveats

1. **Cyfrin training contests are curated answer keys**, designed to be auditable. May overstate any tool's performance vs adversarial contests.
2. **Slither's strength is reentrancy / access-control / structural patterns.** These four corpora are heavy on logic bugs (deadline checks, fee miscalculation, slippage, invariant violations) — Slither's detectors don't target these. The relative result therefore reflects domain fit more than tool quality in absolute terms.
3. **Slither's precision is dragged down by library noise.** Its output was dominated by alerts on forge-std / openzeppelin test harnesses, not the actual protocol code. With proper `--filter-paths lib/` configuration the precision number would improve.
4. **N=4 corpora is small.** plumbline's `c4_ingest.py` has ~1191 ingested Code4rena findings available; a follow-up paper could run this comparison at scale.
5. **Plumbline does require ground-truth answer keys to compute its own self-score** — the 0.76 recall is against the same answer keys, not against a held-out test set. Some optimistic bias possible.
