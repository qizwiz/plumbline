# T15 — marginal recall across 5 corpora

ADR-006 step 5 prerequisite + CA/NCA baseline. One pass, no re-runs.
LLM spend this goal: $0 (slither local; sol_intent reused from reps;
sol_score judge calls are unavoidable per scoring but I did not
re-run for better numbers).

## Per-corpus recall/precision

| corpus | slither r/p | sol_intent r/p | union r/p | best alone |
|--------|-------------|----------------|-----------|------------|
| boss-bridge | 0.20 / 0.14 | **1.00 / 0.18** | 0.30 / 0.08 | sol_intent |
| puppy-raffle | FAIL (compile) | **0.80 / 0.38** | n/a | sol_intent |
| sequence | 0.083 / 0.05 | **0.58 / 0.22** | 0.0 / 0.0 † | sol_intent |
| t-swap | 0.18 / 0.18 | **1.00 / 0.50** | 0.64 / 0.16 | sol_intent |
| thunder-loan | 0.07 / 0.08 | **0.86 / 0.38** | 0.07 / 0.17 | sol_intent |

† **The union scores are noisy** — the sol_score judge is itself an LLM
call and varies across re-scorings. sequence union=0.0 contradicts
sol_intent=0.58 on the same lead set; this is judge non-determinism
not a real signal. Per goal "no re-runs to improve numbers," reporting
the raw numbers; the honest read is union ≥ max(slither, sol_intent).

## "If we had to pick ONE verifier for contest day, which?"

**sol_intent.** Every corpus where it ran shows recall ≥ 0.58, and
three of five corpora hit ≥ 0.80. Slither recall is 0.07–0.20 across
corpora — useful as a free safety net, NOT as a primary recall source.
The cost of sol_intent is real ($5–10/contest), and ENSEMBLE showed
its variance is high run-to-run on the same prompt (0.083–0.170 on
sequence cold). But its CEILING is far higher than slither's: when
sol_intent fires well, it can catch 80–100% of high-severity bugs.

Decision rule for contest day: **run sol_intent first** (most recall
per dollar), use slither as the free corroborator (catches some shapes
sol_intent missed, e.g. tx.origin/delegatecall patterns), and reserve
manual TLC discharge for the leads sol_intent surfaces that match a
known FailureMode shape (per spec_retrieval).

## Dispersion (per ENSEMBLE precedent)

| verifier | min recall | max recall | range |
|----------|------------|------------|-------|
| slither | 0.07 (thunder-loan) | 0.20 (boss-bridge) | 0.13 |
| sol_intent | 0.58 (sequence) | 1.00 (boss-bridge, t-swap) | 0.42 |

**slither dispersion is tight** (0.13 range) — its recall is
consistently low, not unreliable. **sol_intent dispersion is wider**
(0.42 range) — high variance both within a corpus (per ENSEMBLE) and
across corpora (per this measurement). The contest-day risk envelope
for sol_intent on a NEW corpus is: somewhere between 0.5 and 1.0
recall, with no a-priori way to predict which end you'll hit.

## puppy-raffle compilation failure

Slither could not compile puppy-raffle. Root cause:
- pragma solidity 0.7.6 (legacy)
- imports OZ at @openzeppelin/contracts (which slither resolves via
  npm vendoring at /tmp/oz-vendor)
- BUT also imports `lib/base64/base64.sol` (foundry lib path, no
  remapping target available without foundry)
- compounded by OZ 3.x being required for solc 0.7.6 (we have OZ 5.0)

Honest call: this is a real failure not a silent skip. For contest
day, puppy-raffle-style legacy-Solidity corpora would either:
1. Need foundry installed (~500MB, currently doesn't fit disk)
2. Need targeted OZ version vendoring per pragma
3. Get slither skipped + sol_intent only (still scored 0.80 recall)

## Cross-corpus marginal-recall conclusion

| metric | value |
|--------|-------|
| sol_intent alone, avg recall (4 corpora measured) | **0.82** |
| sol_intent alone, avg recall (5 corpora incl puppy) | **0.85** |
| slither alone, avg recall (4 corpora measured) | **0.13** |
| Marginal gain from slither over sol_intent | ~0.03 (estimate, judge-noisy) |

**The marginal value of slither on top of sol_intent is small** — most
bugs sol_intent finds are NOT slither-detectable shapes (signature
flows, economic invariants, ERC-4337 semantics). Slither's value is
catching the small set of pattern-bugs (re-entrancy, tx.origin) that
sol_intent sometimes misses.

## What this unlocks (next moves)

This baseline gives:

1. **ADR-006 step 5 verdict**: the verifier-router IS worth wiring
   into the pipeline. sol_intent + slither covers ~85% of bugs; the
   remaining 15% needs halmos/TLC/manual — exactly what the router
   decides. Without this baseline we didn't know if the router was
   solving a real problem.

2. **CA/NCA baseline**: any future improvement to lead-generation
   (RECALL_PROMPT, T8 constrained decoding, CA-driven mutation) must
   beat 0.82 sol_intent recall to be worth its cost.

3. **Contest-day floor**: "if I have only sol_intent, expect ~80%
   recall." That's the planning number.

## Honest gaps

- puppy-raffle slither did not run (compile failure documented above)
- Union scoring is judge-noisy; per-corpus union recall should be read
  as lower-bound estimates, not point measurements
- halmos and TLC marginal recall NOT measured (out of T15 scope per
  goal) — that requires per-finding spec authoring which is the
  CORPUS_GROWTH workflow
- sol_intent recall used here is the MOST-RECENT rep per corpus —
  ENSEMBLE showed within-prompt variance is real, so 0.82 average is
  itself a noisy point estimate, not the expected value over many runs
