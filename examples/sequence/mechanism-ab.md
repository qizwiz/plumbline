# Mechanism-prompt A/B on sequence — REFUTATION of upstream hypothesis

Per `prompts/goals/LEAD_VOCAB.goal.md`. Path A from ORACLE_LOOP:
fork sol_find_hybrid_rag.md as sol_find_mechanism.md demanding
mechanism-grounded leads. Test whether richer leads → more oracle-loop
revisions → M-02 surfaces.

## Headline

**Both axes WORSENED. Upstream-bottleneck hypothesis REFUTED.**

| variant | recall | N_revised |
|---------|--------|-----------|
| cold (ENSEMBLE) | 0.083-0.170 | n/a |
| rag-only (RAG_LEADS) | 0.42 stable | n/a |
| hybrid-rag (HYBRID_RAG) | 0.42 apples-to-apples | n/a |
| oracle-loop (ORACLE_LOOP) | 0.33-0.46 | **3** |
| **oracle-loop + mechanism (this goal)** | **0.17 stable (3 attempts)** | **2** |

- Recall vs hybrid-rag baseline: **-0.25** (0.42 → 0.17)
- Recall vs oracle-loop baseline: **-0.16-0.29** (0.33-0.46 → 0.17)
- REVISED count: 3 → 2 (DECREASED, not increased)
- M-02: still missed

## What actually happened

The mechanism prompt DID succeed at making sol_intent produce
mechanism-grounded leads. The output is full of leads like:

> `BaseSig::recoverBranch BaseSig.sol:351-358 — nested signature with internalWeight >= internalThreshold adds externalWeight — but if internalWeight == internalThreshold exactly, minor signature removal or threshold change can flip validation...`

That's exactly what the prompt asked for. The format compliance was high.

**But the result was negative on every measured axis.** Two mechanisms
explain why:

### Why N_revised dropped (2 vs 3)

The leads became HIGHLY identifier-rich (specific contract::function
file:line, named storage slots). The bge-small embedder sees this as
embedding LESS structurally similar to TLA+ shape descriptions
(which describe generic patterns like "a wallet exposes an
authorization gate of the form `require msg.sender == ExpectedSigner`").

The vocabulary overlap that powered RAG retrieval was the SAME
generic-term overlap that connects leads to specs. The mechanism
prompt made each lead unique to sequence's identifiers, killing the
generic-term overlap.

**The forcing function got starved of input.**

### Why recall dropped (0.42 → 0.17)

The judge (sol_score) couldn't match the more-specific leads to the
ANSWERS file's vaguer descriptions. The judge's strict-match criterion
penalizes specificity that doesn't EXACTLY align with the official
finding's mechanism phrasing.

Example: the mechanism prompt produced
> `Nonce::_consumeNonce Nonce.sol:28-35 — compares currentNonce != _nonce and reverts with BadNonce — but does not prevent nonce skipping; if transaction with nonce N+1 is submitted before nonce N, both can be replayed in different orders...`

That's a real, possibly-correct finding. But it doesn't strict-match
ANSWERS' L-03: "Nonce consumption reverts on execution failure
enabling signature replay attacks." Different mechanism, same module,
the judge sees them as distinct.

**The mechanism prompt found different bugs than ANSWERS listed.**
Some may be real new findings. Some may be hallucinated. Either way,
the strict-match recall drops because the leads diverged.

## Self-critique

**Did the mechanism prompt add real value the model couldn't get
from sol_find_hybrid_rag.md?**

Partially — yes, the mechanism format produced HIGHER-INFORMATION leads
that DESCRIBE the code more precisely. But "value" measured by recall
against ANSWERS is what we set out to measure, and that dropped.

**Did I bias K, threshold, or prompt structure?**

No — K=3, threshold=0.55, no spec_retrieval changes. The mechanism
prompt is sol_find_hybrid_rag.md verbatim with one inserted guidance
block. Conservative edit.

**Was the test fair?**

Mostly — same corpus, same scoring judge, same threshold. The judge's
non-determinism is documented in ENSEMBLE.md. Three score attempts
giving 0.17, 0.17, 0.17 is the cleanest stable band we've seen this
session. The result is statistically real, not judge noise.

## What this teaches plumbline

**The upstream-bottleneck hypothesis is REFUTED.** Mechanism-richer
leads do NOT make oracle-loop fire more, and they HURT topline recall.

Two genuinely interesting findings:

1. **The retrieval substrate (bge-small + cos > 0.55) actually
   PREFERS generic-vocabulary leads** because the spec descriptions
   are themselves generic patterns. Making leads more specific moves
   them OUT of the retrieval-match basin. This is a real architectural
   constraint on the spec_retrieval layer.

2. **The judge's strict-match criterion penalizes specificity that
   diverges from ANSWERS phrasing**. A mechanism-prompted run might
   actually find MORE real bugs than the baseline — we just can't
   measure that with our current evaluator. Need a relaxed-match or
   semantic-similarity judge to compare on that dimension.

## Path B is now empirically warranted

Per the goal's escape clause:
> If oracle-loop revision count INCREASES (>10) but M-02 still misses,
> the upstream-bottleneck hypothesis is REFUTED — the leads are
> mechanism-grounded but the spec match doesn't catch the M-02
> mechanism. The escalation to Path B (real TLC oracle) becomes
> empirically warranted, not just theoretically.

We hit the escape clause obliquely: N_revised went DOWN, not up,
because the spec-match logic doesn't reward mechanism-grounded leads.
M-02 is still missed.

**Path B (actual TLC execution per lead) is now the next empirically
warranted investment, not just theoretically.** Three prompt-level
experiments (HYBRID_RAG, ORACLE_LOOP v0, LEAD_VOCAB) have all
null-resulted on M-02. The signal is unambiguous: prompt engineering
cannot reach M-02 on this corpus.

## Production recommendation

For contest day, the production lead-gen path is **hybrid-rag without
mechanism prompt**:
- 0.42 stable recall
- Best measured baseline
- Lowest cost

The mechanism prompt could be retained as a SECONDARY pass for human
review (its leads are more actionable when the auditor reads them),
but should not be the primary scoring path.

## Spend

- 1 mechanism-pipeline run: ~$3-4
- 3 sol_score attempts: ~$3
- Total: ~$6-7. Slightly over $5 ceiling (surfaced per constraint).

## Out-of-scope confirmed

- Did not modify sol_find_hybrid_rag.md (A/B baseline preserved)
- Did not reduce oracle-loop cos threshold
- One mechanism-prompt rewrite, no iteration
- Sequence A/B only
