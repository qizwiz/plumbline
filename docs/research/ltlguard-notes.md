# LTLGuard (arxiv 2603.05728) — detailed pipeline notes

Source: arxiv.org/html/2603.05728v1, fetched 2026-06-06.
Saved here because the paper IS the architecture for our TLA+ work and
future-me needs to reference these numbers + design decisions without
re-reading the PDF.

## The 4 levers (ablation study, Table 1)

| Code | Lever | What it does |
|------|-------|--------------|
| **G** | Grammar in prompt | Explicit LTL syntax description in system prompt |
| **S** | SynCode strict decoding | Precomputed DFA mask store; filters invalid tokens at decode-time |
| **R** | RAFSL retrieval | Cosine-similarity retrieval of top-k NL→LTL pairs as few-shot context |
| **F** | Parser feedback | When parse fails, debugging info fed back for iterative refinement |

## Variant-by-variant Mistral-7B (Table 1)

| Variant | Components | Syntactic | Semantic |
|---------|------------|-----------|----------|
| V1 | none (vanilla) | **10.0%** | 7.1% |
| V2 | G | 5.7% | 1.4% |
| V3 | G+S | 15.7% | 5.7% |
| V4 | G+S+R | **87.1%** | 38.5% |
| V5 | G+S+F | 42.8% | 7.1% |
| V6 | S+R+F (no G) | 78.5% | **40.0%** |
| V7 | G+S+R+F (all) | **92.8%** | 38.5% |

**Headline**: Mistral-7B vanilla → 10% syntactic. With S+R+F → 92.8%
syntactic, 40% semantic. **No fine-tuning.**

## Qwen2.5-14B (Table 1)

| Variant | Syntactic | Semantic |
|---------|-----------|----------|
| V1 (vanilla) | 95.7% | 68.5% |
| V4 (G+S+R) | 95.7% | **75.7%** |
| V6 (S+R+F, no G) | 97.1% | **78.6%** |
| V7 (all) | 98.5% | 74.2% |

**Headline**: V6 beats V7 on semantic. Adding grammar to the prompt
(G) actively hurts on the 14B model when S+R+F already in place.

## nl2spec hard benchmark, LTLGuard V6 + Qwen2.5-14B (Table 3)

- Exp. 1 (with overlap): Syntax **100.0%**, Semantic **75.0–77.8%**
- Exp. 2 (no overlap): Syntax 97.2%, Semantic 50.0–63.9%
- Codex interactive ceiling: 86.1%
- Other baselines: 2.7% (NL2LTL) to 58.3%

**Headline**: 14B open model, no fine-tuning, hits 75-78% semantic on
the hard benchmark — within 8 points of Codex interactive.

## CRITICAL DESIGN DECISIONS FOR PLUMBLINE

### Skip G when S is active

V6 (no G) ≥ V7 (with G) on semantic accuracy across both models.
**Adding grammar description to the prompt wastes tokens** when SynCode
already masks bad tokens at decode-time. Our TLA+ prompts should NOT
include TLA+ syntax descriptions when llguidance/XGrammar is wired.

### RAFSL is doing the heavy lifting on semantic accuracy

V4 (G+S+R) gives Mistral 38.5% semantic; V3 (G+S, no R) gives only 5.7%.
**Retrieval is the +33-point lever for semantic accuracy on small
models.** Our 13-spec retrieval corpus is the right primitive; each
verified FailureMode added compounds.

### S is doing the heavy lifting on syntactic validity

V3 (G+S) takes Mistral from 5.7% to 15.7% syntactic — but V4 (G+S+R)
jumps to 87.1%. **The combination of constrained decoding + retrieval
is what hits production-grade syntactic correctness.**

### Atomic-proposition lifting (the subtle one)

RAFSL's index doesn't store raw NL→LTL pairs. They abstract concrete
atomic propositions to generic placeholders (`atom_1`, `atom_2`) so
**retrieval matches structure, not surface tokens.**

For plumbline: when indexing FailureMode descriptions, we should lift
contract-specific identifiers (function names, variable names, contract
names) to generic placeholders. Otherwise retrieval queries about
`L1BossBridge::withdrawTokensToL1` won't return relevant Python-domain
patterns from pact's corpus, and the cross-domain transfer dies.

**Action for T7 / T16**: implement `_lift_idents()` in spec_retrieval.py
that strips contract-specific identifiers before embedding.

### Paraphrasing augmentation

LTLGuard includes paraphrasing to make retrieval robust to alternative
requirement formulations. For our FailureMode descriptions, this means
indexing the SAME bug class under multiple linguistic descriptions
(e.g., "signature replay" + "missing nonce" + "consumed-set absent" all
map to SignatureReplay.tla).

**Action for T16**: when adding a new spec to the corpus, embed
multiple descriptions per spec, not just the header.

### Parser feedback adds marginal value

V5 (G+S+F, no R) is WORSE than V4 (G+S+R, no F) on Mistral semantic.
V7 (all) ≈ V4 + R alone. **Parser feedback is a nice-to-have, not a
must-have**, and it's the most complex piece to wire. Defer.

## Recommended plumbline architecture (LTLGuard-shaped)

Per CLAUDE.md "the superpower" + this synthesis:

```
User asks for FailureMode X.
  │
  ├─ retrieve top-k similar specs from 13-spec corpus (R)
  │   └─ embedded descriptions with contract-identifiers lifted (R')
  │
  ├─ few-shot prompt: just the retrieved examples + bug description
  │   └─ NO TLA+ grammar description in prompt (G skipped per V6 finding)
  │
  ├─ constrained decoding with TLA+ Lark grammar (S)
  │   └─ llguidance or XGrammar — Task T8 / T16
  │
  ├─ candidate spec emerges
  │
  ├─ SANY parse check (cheap; ~1s)
  │   └─ if parse fails, regenerate with shorter context
  │
  ├─ TLC verification (the soundness layer)
  │   └─ if counterexample matches .ANSWERS.md → success
  │   └─ if counterexample doesn't match → spec doesn't capture the bug
  │
  └─ verified spec joins the retrieval corpus
      └─ next FailureMode benefits from it (compounding)
```

## What this DOESN'T do (honest scope)

- **Doesn't predict novel bug classes.** RAFSL retrieves nearest known
  pattern; the LLM adapts. If the contest bug is genuinely novel
  (no nearest-neighbor in corpus), the system performs no better than
  V1 vanilla — which is 10% on Mistral, 95% on Qwen2.5.
- **Doesn't replace verifier discharge.** TLC is the soundness layer.
  The LLM-as-fluency-prosthesis only proposes; correctness comes from
  the model checker.
- **Doesn't close the gap to GPT-5/Claude-Opus-quality models on this
  domain alone.** The 75-78% ceiling is what V6+14B achieves; bigger
  models help (per the Codex 86.1% interactive baseline), but the
  retrieval+decoder architecture is the cheap lever.

## Sources

- Paper: arxiv.org/abs/2603.05728 (v1, Mar 2026 preprint)
- Code: not surfaced in fetch; SynCode + the RAFSL dataset are
  presumably linked from the paper itself
- Caveat: single-paper preprint, self-reported on one benchmark
  (nl2spec). The numbers are plausible but not yet independently
  replicated. Treat 75-78% semantic as **upper bound of what's been
  shown**, not as guaranteed transfer to TLA+ which has a more complex
  grammar than LTL.
