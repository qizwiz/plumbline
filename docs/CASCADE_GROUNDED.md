# Cascade-Grounded Architecture

## What `sol_intent_cascade.py` is

A precision-lifting tool that runs sol_intent only on the ~12 structural
candidates that `structural_cascade.py` flags, rather than all functions.
Cost: ~$0.30/contest (vs ~$1.30 baseline). Output: 12 CONFIRM/REFUTE
verdicts. CONFIRM = high-confidence; REFUTE = discard.

**It is NOT a replacement for baseline sol_intent.** It is a precision
confirmer.

## The calibration result (2026-06-08, Notional Exponent)

| mode | leads | recall (all H+M) | recall (H-only) | est precision |
|---|---|---|---|---|
| baseline (`sol_intent --hybrid-rag --recall`) | 205 | 67.6% | 81.8% | 13.7% |
| cascade-grounded (`sol_intent_cascade.py`) | 12 | 5.4% | 0.0% | ~50%+ |

**Root cause of the recall collapse**: Notional's 11 Highs are
protocol-integration bugs (Pendle PT oracle, Morpho path edge, Curve
migration, etc.) — none match plumbline's 9 TLA+ shapes. The cascade
filtered out everything that didn't match a known shape. Max possible
recall for cascade on Notional was ~14%.

## The right contest-day architecture: UNION

```
                ┌─→ sol_intent.py --hybrid-rag --recall  ──→ broad leads
contest scope ──┤                                         (high recall, low precision)
                │
                └─→ tools/sol_intent_cascade.py  ─────────→ focused verdicts
                                                          (high precision on shape-match bugs,
                                                           low recall on diverse-bug contests)

                                     ↓
                          UNION + tag confidence:
                          - cascade CONFIRMs → confidence=HIGH (prioritize in triage)
                          - baseline leads not in cascade → confidence=NORMAL
                          - cascade REFUTEs → deprioritize ("don't waste time" signal)
```

Run BOTH. Triage cascade CONFIRMs first (highest confidence, fewest leads).
Fall back to baseline leads for everything else.

## The real gap-closer: shape library expansion

The 93.7% Sherlock corpus coverage measured by RAG is **thematic** — the
RAG has broad priors across many bug classes. The cascade narrows to bugs
matching one of 9 formal TLA+ shapes. These are different gates.

To lift cascade recall from ~14% to 80%+ on Notional-style contests,
the shape library needs ~6-10 new entries:

| shape | target bug class | example contest |
|---|---|---|
| OracleStaleness | stale price / TWAP manipulation | Notional H-8 |
| IntegrationAssumptionMismatch | chain-specific addr, Pendle conventions | Notional H-8 |
| RewardAccountingMigration | storage layout drift on upgrade | Notional H-5 |
| LiquidationRaceCondition | race on liquidation window | general |
| WithdrawRequestOverlap | double-claim on withdraw queue | Notional H-3 |
| HardcodedDeployParam | WETH addr, useEth flag | Notional H-9 |

Each takes ~1 day: TLA+ spec + TLC verification + cascade Layer A query +
Foundry PoC template. Budget in CORPUS_GROWTH.goal.md or future goal rows.

## Files

- `tools/sol_intent_cascade.py` — the tool
- `prompts/sol_find_cascade.md` — candidate-grounding prompt
- `corpus/calibration/CALIBRATION_CASCADE_GROUNDED.md` — full measurement writeup
- `corpus/calibration/notional-cascade-leads.txt` — 12 verdicts
- `corpus/calibration/notional-cascade-score.json` — scored output
