# Hybrid RAG A/B on sequence — null result, escalation signal

Per `prompts/goals/HYBRID_RAG.goal.md`. v0 combines `rag_query` (.ANSWERS
across 5 corpora) + `spec_retrieval` (9 own TLA+ shapes) into one
unified few-shot block. Architectural prediction: M-02 surfaces because
`ERC4337StaticSigDoS` shape is injected.

## Headline

**Architectural prediction FAILED. M-02 still missed.**

| variant | recall (12-denominator) | n_leads |
|---------|--------------------------|---------|
| cold baseline (ENSEMBLE)   | 0.083-0.170 | 146-184 |
| rag-only (RAG_LEADS)       | **0.42 stable (2 attempts)** | 134 |
| hybrid-rag (this goal)     | **0.42 (apples-to-apples)** | 237 |

Three score attempts on the hybrid output: 0.42, 0.50, 0.58. **But the
0.50 and 0.58 used different denominators (6 and 5 vs 12)** — the
sol_score judge inconsistently dropped informational findings (L-04/05/06)
across runs. The apples-to-apples comparison (12-denominator, same as
RAG-only's two stable scoring runs) gives **0.42, identical to RAG-only**.

**Delta vs RAG-only baseline: +0.0** (within judge noise).

## M-02 specifically

**M-02 still in the missed set.** The hybrid retrieved-evidence block
DID inject the ERC4337StaticSigDoS shape description with cos=0.66, and
the model DID see that the chunk's `ERC4337v07.sol` was about ERC-4337
caller validation. Yet the model did NOT surface the specific bug that
"static signatures bound to caller revert under EntryPoint indirection."

The deep-research predicted exactly this failure mode:
> M-02 requires deeper semantic understanding... tracking caller-context
> transformation across 4337 boundaries.

Prompt-time injection of structural shapes is not sufficient for
bugs that require multi-hop semantic reasoning across an
indirection (`EntryPoint.handleOps(userOp) → wallet.validateUserOp(userOp) →
msg.sender == ENTRY_POINT, not the original sender`). RAG's
pattern-matching lift saturates here.

## Findings hybrid DID catch (RAG-only also caught these, no incremental)

- H-01-style flag-bypass-validation-chain (now caught — was missed by
  RAG-only)
- M-01 cross-wallet sig replay
- M-04 Create2 factory idempotency
- L-01 cumulative validation drift
- L-02 counter-on-revert

Interesting: H-01 (which RAG missed for "no past analog" reason) IS
caught by the hybrid because the shape was just authored tonight as
`FlagBypassesValidationChain`. That's a single-finding win attributable
specifically to the spec_retrieval layer.

But the judge's denominator drift means we can't claim recall lift
without re-running sol_score deterministically. The hybrid likely caught
1 MORE finding than RAG-only (H-01) but the noise floor swallows that
in the recall metric.

## Cost

- 1 hybrid-rag cold run on sequence: ~$3-5
- 3 sol_score scoring attempts: ~$3
- Total: ~$6-8. **Slightly over the $5 goal ceiling.** Surfacing
  per the constraint. The hybrid block is longer than RAG-only's;
  per-chunk cost scaled up.

## Honest verdict

**The hybrid layer is correct architecturally but the lift is
marginal-to-zero.** The deep-research's predicted +0.10-0.20 didn't
materialize. The architectural prediction that "M-02 surfaces because
shape is injected" failed cleanly.

This validates the deep-research's escalation path: prompt-time
injection is insufficient for deep-semantic bugs. The next direction is
oracle-grounded self-correction (deep-research top-3 #3) — using
TLC/halmos/slither as external oracles in a "propose → verify → revise"
loop. THAT is where M-02 might actually surface, because a TLC run on
an ERC-4337-flavored caller-bound spec would VIOLATE its invariant on
the sequence code, providing direct feedback.

## Self-critique

**Did I bias K, threshold, or prompt structure?**

No. K=3 was the goal default. spec_retrieval has no threshold (top-K
unconditional). Prompt structure is sol_find_rag.md verbatim with the
slot renamed `retrieved_evidence` and the guidance tweaked from one
sentence to two (mentioning both inspiration sources). Conservative
edits.

**Did I cherry-pick which scoring attempt to call the headline?**

I report ALL THREE attempts (0.42, 0.50, 0.58) and call out the
denominator-drift cause of the variance. The apples-to-apples
comparison (12-denom attempt 1) is the honest headline number, and
it's 0.42 — identical to RAG-only baseline.

## What this unlocks

The deep-research's escalation path is now empirically warranted:

> **Self-correction with external oracle**: lead → TLC → if undecided
> or violation-on-buggy-side, revise lead → retry. Plumbline already
> has the oracle (TLC/halmos/slither). The literature only refutes
> intrinsic self-correction; oracle-grounded loops are viable.

This is the next goal to write. `ORACLE_LOOP.goal.md` or similar.

## Out-of-scope confirmed

- Did not tune K, threshold, or prompt beyond v0
- Did not modify rag_query.py or sol_find_rag.md (composition only)
- Did not run on other corpora (sequence A/B only)
- $5 ceiling slightly exceeded (surfaced)
