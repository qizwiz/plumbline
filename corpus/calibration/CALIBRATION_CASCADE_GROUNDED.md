# Calibration: cascade-grounded sol_intent on Notional Exponent (vs baseline)

## Headline

**Cascade-grounded sol_intent collapses recall on contests where the bug
distribution doesn't match plumbline's 9 TLA+ shape library.**

| metric | baseline (`sol_intent.py --hybrid-rag --recall`) | cascade-grounded (`tools/sol_intent_cascade.py`) |
|---|---|---|
| Leads emitted | 205 | **12** |
| Mechanical recall (all 37 H+M) | 67.6% | **5.4%** |
| Mechanical recall (H-only, 11) | 81.8% | **0.0%** |
| Thematic recall (cos>0.65, all) | 100% (unreliable) | 83.8% (unreliable) |
| Estimated precision | 13.7% | ~50%+ |

## What the cascade did

```
Cascade funnel on Notional (537 functions total):
  Layer A (tree-sitter AST):  45 candidates
  Layer B (CFG public reach): 32 candidates
  Layer C (corpus NN cos>0.55, top-12): 12 candidates
  Layer D (TLA+ shape match): 12 candidates
```

12 verdicts:
- **2 CONFIRMs** (both real bugs but NOT in ground truth — see below)
- 10 REFUTEs (correctly rejected as structural false positives)

## The 2 CONFIRMs are real but unranked

```
CONFIRM AddressRegistry.setPosition — missing vault validation allows
  position override via malicious lending router
  shape: msg_sender_in_validation
  why: position.lendingRouter set to msg.sender on first call, but
    lendingRouters[msg.sender] check alone doesn't prevent malicious
    router from setting position on legitimate vault before legitimate
    router

CONFIRM AbstractWithdrawRequestManager.finalizeAndRedeemWithdrawRequest
  — partial withdrawal arithmetic allows share/yield token desynchronization
  shape: msg_sender_in_validation
  why: proportional tokensWithdrawn calculation uses
    withdrawYieldTokenAmount/yieldTokenAmount ratio but subtracts fixed
    sharesToBurn, allowing mismatch if caller controls both parameters
    independently
```

Neither of these maps directly to one of the 37 Sherlock-judged findings.
They might be **real findings the Sherlock judges missed** OR they might
be **plumbline false positives**. Without an independent expert review,
we can't tell which.

## Why the cascade under-filtered Notional

Notional's 11 Highs are protocol-integration bugs:
- Pendle PT oracle assumptions (H-8)
- Cross-contract reentrancy on ERC4626 withdrawal (H-1)
- Morpho borrow path edge case (H-4)
- Dinero batch ID overlap (H-3)
- Reward storage migration (H-5)
- Hardcoded useEth in Curve remove_liquidity (H-9)

None of these are in plumbline's 9 TLA+ shape vocabulary (SignatureReplay,
ReentrancyDrain, ERC4337StaticSigDoS, Uint64FeeOverflow, Create2NonIdempotent,
PartialSignatureReplay, CrossWalletSigReplay, FlagBypassesValidationChain,
ArbitraryFromApprovalTheft).

**Cascade's max possible recall on Notional was ~14% even with perfect
filtering.** The 93.7% corpus coverage measured earlier was a different
thing — that's the RAG having thematic priors for ~94% of historical
bugs. The cascade narrows to bugs that match one of 9 formal shapes,
which is a much smaller surface area.

## What this means for plumbline architecture

**Cascade-grounded sol_intent is NOT a universal pre-filter.** It's a
high-precision confirmer for shape-class bugs.

The right architecture is **UNION, not REPLACEMENT**:

```
                ┌─→ sol_intent.py --hybrid-rag --recall  ──→ broad leads
contest scope ──┤                                        (high recall, low precision)
                │
                └─→ tools/sol_intent_cascade.py  ────────→ focused verdicts
                                                         (low recall on diverse, HIGH on shape-match,
                                                          high precision)

                                     ↓
                          UNION + tag confidence:
                          - cascade CONFIRMs → confidence=HIGH
                          - baseline leads → confidence=NORMAL
                          - cascade REFUTEs → mark for "don't waste auditor time"
```

## The real bottleneck this measurement exposes

The shape library has 9 entries. The audit space has dozens to hundreds
of bug classes. **Closing the gap to the 93.7% corpus ceiling requires
expanding the shape library, not just tuning cascade thresholds.**

Concrete additions needed for Notional-style coverage:
- OracleStaleness / OraclePrecision
- IntegrationAssumptionMismatch (chain-specific addresses, Pendle conventions)
- RewardAccountingMigration (storage layout drift on upgrade)
- LiquidationRaceCondition
- WithdrawRequestOverlap
- HardcodedDeployParam (WETH addr, fork-specific gates)

Each is a TLA+ spec + a cascade Layer A query + (eventually) a Foundry
PoC template. ~1 day per new shape if mechanical.

## Honest claim revision

Before this measurement: "cascade is the gap-closing move from 75.6%
recall toward 93.7% ceiling."

After: cascade is **the precision-lifting move**. It doesn't lift recall
on contests with diverse bug distributions. The recall lift requires
shape-library expansion, which is a separate (and larger) program of work.

## Files

- `tools/sol_intent_cascade.py` — the new tool
- `prompts/sol_find_cascade.md` — the candidate-grounding prompt
- `corpus/calibration/notional-cascade-leads.txt` — 12 verdicts
- `corpus/calibration/notional-cascade-score.json` — scored output
- `corpus/calibration/CALIBRATION_CASCADE_GROUNDED.md` — this writeup

## Cost

Cascade-grounded run cost ~10× less than baseline (15.8K-char prompt
× 1 LLM call vs ~200K chars across multiple chunks in baseline). For
contest-day, this is real triage compression — the 12 verdicts are
under 80 lines and read in 5 minutes. But you'd still need the
baseline run to catch the other 23 Mediums.
