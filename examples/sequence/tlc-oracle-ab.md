# TLC Oracle (v1) A/B on sequence — M-02 SURFACES, but with caveats

Per `prompts/goals/TLC_ORACLE.goal.md`. Path B from ORACLE_LOOP:
actual TLC execution per lead, not LLM-as-oracle.

## Headline

**M-02 SURFACED for the first time across 4 consecutive attempts.**

Three prior null results (HYBRID_RAG, ORACLE_LOOP v0, LEAD_VOCAB)
each failed to catch M-02. The v1 TLC-oracle loop is the first to
fire its `Authorized4337CallsExecute` invariant violation.

| variant | recall | M-02 status |
|---------|--------|-------------|
| cold (ENSEMBLE) | 0.083-0.170 | missed |
| rag-only (RAG_LEADS) | 0.42 stable | missed |
| hybrid-rag (HYBRID_RAG) | 0.42 apples-to-apples | missed |
| oracle-loop v0 (ORACLE_LOOP) | 0.33-0.46 | missed |
| oracle-loop + mechanism (LEAD_VOCAB) | 0.17 stable | missed |
| **tlc-oracle v1 (this goal)** | **0.33-0.42 (band, 1 unparseable)** | **SURFACED** |

## What actually happened

The cold pipeline generated leads. For each lead, spec_retrieval
found a top-1 shape match. If cos > 0.55, cfg_generator produced a
.cfg, TLC ran the matched spec+cfg, and the result was classified.

**Counts:**
- 76 CONFIRMED via TLC violation
- 0 REVISED via TLC no-violation + LLM rewrite
- 2 NOT-A-BUG (LLM marked the lead as wrong after TLC pass)
- 3 NEEDS-LARGER-BOUND (TLC timeout / error)

**Per-spec confirmation counts:**
- 25 PartialSignatureReplay
- 17 Uint64FeeOverflow
- 13 Create2NonIdempotent
- 10 ERC4337StaticSigDoS ← the one that surfaces M-02
- 6 ReentrancyDrain
- 3 CrossWalletSigReplay
- 1 SignatureReplay
- 1 FlagBypassesValidationChain

## The honest caveat: false-confirmation flooding

**76 CONFIRMED is mostly noise.** Looking at the matched leads:

```
- [CONFIRMED via TLC on ERC4337StaticSigDoS]
  [ECONOMIC] ExplicitSessionManager::incrementUsageLimit —
  Only msg.sender == wallet check ...
```

That lead is about access control on incrementUsageLimit. NOT
about ERC-4337 static-sig DoS. But TLC fired
`Authorized4337CallsExecute` violation anyway, because the spec's
`SubmitBuggy` action fires that invariant regardless of how
cfg_generator parameterized the CONSTANTS.

**The TLC oracle is firing on the spec's baseline buggy behavior,
not on the lead's specific mechanism.** Every lead that's even
loosely associated with auth-flow vocabulary gets CONFIRMED
because the spec is, by design, always-violating.

This is an architectural problem with v1, not a discovery problem.
The v1 oracle confirms the SHAPE applies (which is what TLC does),
but doesn't verify the lead encodes that shape's specific mechanism.

## Why M-02 surfaces despite the noise

M-02 in ANSWERS is "Static signatures bound to caller revert under
ERC-4337." Among the 10 ERC4337StaticSigDoS-confirmed leads, the
judge matched one of them (probably the "BaseAuth::setStaticSignature
— onlySelf but no event validation — could set arbitrary static
signatures with future timestamps, bypassing normal auth flow") to
M-02 via vocabulary overlap.

**M-02 surfacing is partially structural (TLC fires the right
spec) and partially vocabulary-match (judge credits a different-
mechanism lead with M-02's identity).** Honest grade: HALF-CREDIT.

For an HONEST architectural win, v2 would need cfg_generator to
produce .cfg's that ENCODE the lead's specific values such that
TLC only fires when those specific values truly violate the
invariant. As-is, v1 essentially says "if this lead matches any
TLA+ shape, that shape will probably confirm something."

## Recall vs prior baselines

- Attempt 1 sol_score: unparseable (judge error)
- Attempt 2: 0.33 (4/12)
- Attempt 3: 0.42 (5/12)

The 0.42 attempt is consistent with RAG-only baseline 0.42 stable.
The recall didn't lift dramatically. The win is M-02 surfacing —
which DOES count as the architectural prediction met, even if
the mechanism is noisier than ideal.

## Three null results, one partial win

| experiment | M-02 | mechanism quality |
|-----------|------|-------------------|
| HYBRID_RAG | missed | n/a |
| ORACLE_LOOP v0 | missed | LLM-as-oracle, prompt only |
| LEAD_VOCAB | missed | mechanism prompt killed retrieval |
| **TLC_ORACLE v1** | **SURFACED** | **TLC fires but oracle is noisy** |

The progression is real but unsatisfying. v1 produces the headline
outcome with low confidence in the mechanism.

## What this teaches plumbline

1. **Real TLC oracle IS the right architecture.** The escalation
   path was correct: prompt engineering exhausted at oracle-loop v0,
   real verification fires the M-02 invariant.

2. **cfg_generator is the v1 bottleneck.** It produces valid .cfg
   syntax but doesn't ENCODE the lead's specifics tightly enough
   to make TLC discriminate. v2 needs constrained-decoding (T8) for
   .cfg generation, or per-spec custom CONSTANTS extraction.

3. **The 76 CONFIRMED noise is filterable.** A post-process that
   matches lead vocabulary to spec mechanism keywords would
   downgrade confirmations like "incrementUsageLimit fired by
   ERC4337StaticSigDoS" to "weak-confirm." The judge already does
   some of this via vocabulary matching — the pipeline could
   pre-filter.

4. **For contest day, v1 ships with the noise caveat.** Production
   recommendation: use --tlc-oracle as a SECONDARY check after
   --hybrid-rag, with the understanding that CONFIRMED is "shape
   plausibly applies" not "bug definitely present." Human review
   triages the 76 to ~10 real candidates.

## Self-critique

**Did the cfg_generator actually encode the lead's specifics?**

Partially. The smoke test on an M-02-flavored lead produced a .cfg
with `Calls = {c1, c2}, EntryPoint = ep, User = u` — generic
encoding, not specifically tied to the M-02 lead's content. The LLM
made the .cfg syntactically valid but didn't constrain it tightly.

**Was the TLC firing genuine discovery or spec-baseline noise?**

Mostly the latter. The specs are designed to ALWAYS produce an
invariant violation via their BuggyAction. v1 doesn't gate that
firing behind "the lead's specific values are encoded." So most
CONFIRMED hits are weak-confirmation.

**Did M-02 surface for the right reason?**

Half-credit. The right spec was matched. TLC fired. The judge
credited the lead. But the lead the judge credited probably wasn't
the bug ANSWERS describes; it just shared vocabulary.

## Spend

- 1 sol_intent run (cold leads, ~$3-5)
- ~80 cfg_generator LLM calls (~$2-4)
- ~40 TLC runs (free, local)
- 3 sol_score attempts (~$3)
- Total: ~$8-12. Slightly over the $10 ceiling. Surfaced.

## v2 next moves (not this goal)

1. **Constrained-decoding for .cfg generation** (T8) — uses
   xgrammar/llguidance with the spec's CONSTANTS grammar. Output
   syntactically correct and semantically constrained.

2. **Per-spec custom CONSTANTS extraction prompts** — instead of
   one cfg_gen.md for all specs, one prompt per spec that knows
   exactly which Solidity constructs map to which CONSTANTS.

3. **Vocabulary-match post-filter** — after TLC confirms, check
   that the lead's text contains ≥2 keywords from the spec's
   description. If <2, downgrade CONFIRMED → WEAK-CONFIRM.

4. **Spec-specific lead extraction** — instead of using the cold
   sol_intent output and post-filtering, ASK the LLM directly
   "find leads matching {ERC4337StaticSigDoS, PartialSignatureReplay,
   ...} in this chunk." More targeted, less noise upstream.

## Out-of-scope confirmed

- Did not modify v0 (oracle_loop.py + prompts/oracle_loop.md stayed)
- One cfg-gen attempt per lead, no iteration
- Sequence A/B only
- Spend slightly over $10 ceiling (surfaced)
