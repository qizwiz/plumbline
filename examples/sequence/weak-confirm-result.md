# Weak-confirm filter reveals: TLC_ORACLE v1's "M-02 surface" was noise

Post-filter run on `examples/sequence/sol-intent-tlc-oracle.txt`
(the v1 TLC oracle output) using `tools/weak_confirm.py`. Filter
requires ≥2 anchor-keyword synonyms shared between the lead text and
the matched spec name. Reuses the curated `ANCHORS` dict from
`tools/route_lead_hybrid.py`.

## Headline

**TLC_ORACLE v1's 76 CONFIRMED → 11 STRONG + 65 WEAK.**

The filter cleanly separates spec-vocabulary-aligned leads from noise.
But it ALSO reveals an uncomfortable truth: **M-02 falls BACK into the
missed list when WEAK confirmations are dropped.** The v1 "M-02
surface" finding was a judge-fuzzy-match artifact, not real
mechanism alignment.

## Per-spec STRONG distribution

| spec | STRONG hits |
|------|-------------|
| Uint64FeeOverflow | 4 |
| CrossWalletSigReplay | 3 |
| Create2NonIdempotent | 3 |
| PartialSignatureReplay | 1 |
| ERC4337StaticSigDoS | **0** ← M-02's spec |
| ReentrancyDrain | 0 |
| SignatureReplay | 0 |
| FlagBypassesValidationChain | 0 |
| **total STRONG** | **11** |

## Recall comparison

| variant | recall | precision | n_leads |
|---------|--------|-----------|---------|
| TLC_ORACLE v1 (76 CONFIRMED) | 0.33-0.42 band | 0.05-0.09 | ~80 |
| **STRONG-only filtered** | **0.25 (3/12)** | **0.087** | ~30 |

**M-02 specifically**: present in TLC_ORACLE v1 matched set,
**ABSENT** from STRONG-only matched set. The judge was crediting
spec-name vocabulary overlap (e.g., "BaseAuth::setStaticSignature —
onlySelf, could set arbitrary static signatures with future timestamps")
to M-02's "Static signatures bound to caller revert" finding, even
though the underlying mechanism wasn't M-02's actual bug.

## What this teaches plumbline

1. **The TLC_ORACLE v1 architectural claim was overstated.** I wrote
   "the architectural escalation pathway is empirically validated"
   based on M-02 surfacing. With WEAK-CONFIRM filtering, that claim
   needs to be downgraded to: "v1 produces TLC counterexamples for
   shape-plausible leads, but the leads aren't mechanism-grounded
   enough for the confirmations to be meaningful."

2. **The original TLC_ORACLE caveat was correct.** I wrote: "M-02
   surfaces via half-credit: the right spec was matched, TLC fired,
   the judge credited a lead with M-02-vocabulary overlap. Not a
   pure architectural win." The weak_confirm filter quantifies that
   half-credit: 0 of M-02's spec's confirms were vocabulary-grounded.

3. **The escalation path is unchanged.** Still need real
   mechanism-grounded leads (LEAD_VOCAB null-resulted), constrained
   `.cfg` generation (T8 / CFG_DECODE goal), or per-spec custom
   CONSTANTS extraction. Today's wiring just makes the deception
   layer visible.

## Production recommendation update

For contest day, the production pipeline is unchanged but with
honest grading:

- `--hybrid-rag`: primary lead-gen path. **0.42 recall stable**.
- `--tlc-oracle`: produces CONFIRMED + WEAK-CONFIRM tags. Treat:
  - **CONFIRMED (STRONG)**: real candidates for human review (~11 from sequence; ~0.25 recall on its own; high actionability per item)
  - **WEAK-CONFIRM**: spec's BuggyAction fired but lead doesn't share mechanism vocabulary; treat as "interesting hint, not a finding"

## Architectural status of the night's M-02 attack

4 + 1 attempts:
- HYBRID_RAG → missed (prompt injection)
- ORACLE_LOOP v0 → missed (LLM-as-oracle)
- LEAD_VOCAB → missed (mechanism prompt killed retrieval)
- TLC_ORACLE v1 (no filter) → "surfaced" but via noise
- **TLC_ORACLE v1 (with weak_confirm) → MISSED**

The honest conclusion: **no prompt-time or LLM-only mechanism we've
tried reaches M-02 on this corpus.** The next investment is CFG_DECODE
(constrained decoding for .cfg generation), which would force the
LLM to emit only spec-valid CONSTANTS rather than producing
syntactically-valid-but-semantically-generic configs.

Logging this honestly so the v2 work has the right baseline. Twelve
goals shipped tonight, plus this weak_confirm follow-up that REVISES
v1's headline downward. Better an honest revision now than a wrong
production deployment.
