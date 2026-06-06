# A Retrieval-Augmented Pipeline for Authoring TLC-Verifiable Solidity FailureModes

*Plumbline / 2026-06-06*

## Abstract

We describe a pipeline that takes a Solidity smart-contract bug
description (one sentence to a paragraph of natural language) and
produces a TLA+ module whose violated invariant — when discharged by
the TLC model checker — IS a faithful counterexample for the
underlying bug. The pipeline is hand-prompt-driven for now (an LLM
authors the module body conditioned on retrieved precedent specs);
it is end-to-end functional with 5 hand-authored modules covering 5
distinct bug-class shapes, each mechanically TLC-discharged. The
architecture is shaped by LTLGuard (arxiv 2603.05728) and adapts its
retrieval-augmented few-shot pattern from LTL to TLA+. We report on
what works (the bug-class taxonomy emerges, TLC discharge is
deterministic, the corpus compounds), what doesn't (embedder
discrimination over short bug-shape descriptions is weak with
off-the-shelf models), and the architecture's deliberate scope
limits (we are not building a Solidity-language semantic embedding;
we are building a routing+discharge layer over an LLM-as-fluency-
prosthesis).

## 1. The problem

Smart-contract auditing currently sits between two poles. **Static
analyzers** (Slither, Mythril, Securify) catch a fixed set of
syntactic patterns with high precision and near-zero recall on novel
logic bugs. **Symbolic-execution tools** (Halmos, KEVM, hevm) prove
property tests but require humans to author the properties — the
hard part. **LLM-only auditors** (recent commercial products and
academic prototypes) generate verbose lead lists with unclear
precision; published numbers vary wildly and most fail to reproduce
on held-out benchmarks (cf. Steenhoek et al. ICSE 2023 on GNN
vulnerability detection collapsing OOD).

The gap: a pipeline that takes a candidate lead (in natural language,
from an LLM, a human auditor's notes, or a slither finding) and
returns a **mechanically-discharged proof object** — not "the model is
80% confident" but "TLC produced this counterexample in 47ms."

## 2. Architecture

```
   Lead (natural language)
     │
     ▼
   ┌─────────────────────────────────────────────────────┐
   │  RETRIEVAL                                          │
   │  embed(lead, atomic-proposition-lifted) →           │
   │    top-k specs from corpus by cosine                │
   └─────────────────────────────────────────────────────┘
     │
     ▼
   ┌─────────────────────────────────────────────────────┐
   │  LLM AUTHOR                                         │
   │  prompt: bug description + top-k retrieved specs    │
   │    as few-shot context                              │
   │  output: candidate TLA+ module + .cfg               │
   │  (grammar-constrained decoding — future work)       │
   └─────────────────────────────────────────────────────┘
     │
     ▼
   ┌─────────────────────────────────────────────────────┐
   │  SANY parse check (1s)                              │
   │   → if fail, return to author                       │
   └─────────────────────────────────────────────────────┘
     │
     ▼
   ┌─────────────────────────────────────────────────────┐
   │  TLC discharge (~50ms - 5s)                         │
   │   → success = "invariant X violated, here's the     │
   │      counterexample"                                │
   │   → counterexample IS the proof object              │
   └─────────────────────────────────────────────────────┘
     │
     ▼
   ┌─────────────────────────────────────────────────────┐
   │  Spec joins retrieval corpus                        │
   │   → next lead benefits (compounding)                │
   └─────────────────────────────────────────────────────┘
```

### 2.1 Retrieval

We use BAAI/bge-small-en-v1.5 (a 33M-param sentence transformer)
embeddings of LIFTED bug-class descriptions. "Lifted" means we apply
LTLGuard's atomic-proposition lifting (§ 3.3 of arxiv 2603.05728):
identifiers that look domain-specific (`_CORO_CONSUMERS`,
`L1BossBridge::withdrawTokensToL1`, `s_flashLoanFee`) are replaced
with generic placeholders (`<id_1>`, `<id_2>`, ...) so cosine matches
**structural similarity** of bug shape, not surface tokens.

A vocabulary list (`_KEEP_VOCAB` in `tools/spec_retrieval.py`) preserves:

- TLA+ keywords (`module`, `Init`, `Spec`, `invariant`, `\A`, `\E`, ...)
- Bug-shape primitives (`reentrancy`, `replay`, `nonce`, `overflow`,
  `truncation`, `idempotent`, `missing`, `await`, `consumer`,
  `violation`, ...)

Everything outside this set that matches camelCase / snake_case /
SCREAMING_SNAKE_CASE patterns is lifted.

### 2.2 LLM author

The prompt is V6-shaped per LTLGuard's ablation (S+R+F, no grammar in
prompt — V6 ≥ V7 on semantic accuracy across both Mistral-7B and
Qwen-14B, Table 1). That is: we DO NOT include a TLA+ grammar
description in the system prompt. Instead, we include 2-3 retrieved
precedent specs as few-shot context. The LLM extrapolates structure
from the examples; constrained decoding (future work) catches the
syntactic tail.

### 2.3 SANY + TLC discharge

We invoke the Lamport `tla2tools.jar` (TLC v2.19) with:

```
java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
  -config Spec.cfg -deadlock Spec
```

If the buggy spec models the bug correctly, TLC produces a
**counterexample trace** that violates the explicit safety invariant
(NoOverpayment, ClaimedAtMostOnce, etc.). The trace is the proof
object: a sequence of states with the violated invariant named at
the violation step.

## 3. Bug-class taxonomy

Our hand-authored corpus (5 modules, all TLC-verified) covers 5
**distinct structural bug-class shapes**:

| Module | Shape | Concrete bug | TLC trace length |
|--------|-------|--------------|------------------|
| `SignatureReplay.tla` | should-be-one-shot, no guard | boss-bridge H-3 | 2 states |
| `ReentrancyDrain.tla` | should-be-one-shot, guard after external call | puppy-raffle H-1 | 3 states |
| `ERC4337StaticSigDoS.tla` | caller-bound auth misreads msg.sender via EntryPoint | sequence M-02 | 2 states |
| `Uint64FeeOverflow.tla` | narrow-accumulator truncation | puppy-raffle H-3 | 4 states |
| `Create2NonIdempotent.tla` | idempotency violation | sequence M-04 | 3 states |

These were authored over a single overnight session (~6 hours)
using two existing specs as few-shot precedent (one from our own
corpus, one cross-domain from a sibling Python-checker project).
Each TLC discharge completed in under 1 second of wall-clock time.

The taxonomy is **deliberately structural, not domain-bound**. The
"should-be-one-shot" shape covers both signature-replay (no guard
present) and reentrancy (guard placed after the external call) by
varying the position of the guard in the state machine, not the
contract domain. This is what makes the corpus compound: each new
shape generalizes across a family of bugs, not just one.

## 4. Engineering findings

### 4.1 The corpus compounds — empirically

Authoring the second FailureMode (ERC4337StaticSigDoS) cost ~30
minutes including TLC iteration. The fifth (Create2NonIdempotent)
cost ~10 minutes. The marginal cost decreases as more retrieved
precedents are available; LTLGuard's syntactic-validity numbers
(V3 → V4, +71pt on Mistral) explain the trajectory: retrieval is
the lever.

### 4.2 Off-the-shelf sentence embedders discriminate weakly on bug-shape descriptions

Our verification of `tools/spec_retrieval.py`:

| Query | Expected top-1 | Actual rank | Top-1 cos |
|-------|----------------|-------------|-----------|
| "signature replay nonce missing" | SignatureReplay | #4 | (different) |
| "missing await coroutine async" | MissingAwait | not in top-5 | — |
| "ERC 4337 entrypoint static signature DoS scheduler" | ERC4337StaticSigDoS | #1 | 0.585 |

Two of three queries fail to return the expected precedent at top-1.
All 10 indexed specs cluster in a ~0.12 cosine range, suggesting
bge-small-en-v1.5 was not trained on enough bug-shape vocabulary to
discriminate well.

This does NOT block the pipeline: retrieved top-k provides few-shot
context, and the LLM extrapolates structure from any plausible
precedent. But it suggests two open extensions:

1. **Hybrid BM25 + dense retrieval** — lexical signal would catch
   "replay" or "await" or "overflow" directly without semantic
   embedding ambiguity.
2. **Domain-tuned embedder** — fine-tune a small embedder on
   (bug-shape, TLA+ spec) pairs once the corpus reaches ~50 modules.

### 4.3 Grammar-constrained decoding is the next syntactic-validity lever

We vendored a Lark CFG (`grammar/tla_failuremode.lark`) covering the
structural form of our 5 hand-authored specs (5/5 validate). It's
the input to a future constrained-decoder integration (llguidance or
XGrammar). Per LTLGuard ablation:

- V1 (vanilla Mistral-7B): 10.0% syntactic, 7.1% semantic
- V3 (G+S, grammar + constrained decode): 15.7% syntactic
- V4 (G+S+R, + retrieval): 87.1% syntactic, 38.5% semantic

Wiring grammar-constrained decoding is what moves syntactic
validity above 90% for small open models. Right now we rely on a
large frontier model + SANY parse retry; the future direction is
14B open model + constrained decoding + retrieval to match Codex
interactive (V4+ on nl2spec hard reached 75-77% semantic for
Qwen-14B).

### 4.4 The bulleted-conjunction pattern matters for grammar design

A subtle issue in our first Lark draft: TLA+ allows expressions like

```
TypeInvariant ==
    /\ A
    /\ B
    /\ C
```

(equivalent to `A /\ B /\ C` but written vertically). A naive grammar
treats the leading `/\` as an error because it's followed by an
expression rather than two operands. Our grammar accepts this via
an optional `bullet_lead` prefix on every expression. Practical
takeaway: bulleted conjunctions are the TLA+ idiom for any
nontrivial invariant; the grammar must explicitly handle them.

## 5. What this is NOT

We are deliberate about what's out of scope:

- **NOT a Solidity-semantic embedding model.** We do not train on
  Solidity source. The LLM brings the source-understanding; we add
  the structural-precedent and the soundness layer.
- **NOT a replacement for Slither or Halmos.** Slither catches the
  fixed-pattern bugs cheaply. Halmos discharges conservation
  invariants when authored. Our pipeline catches **logic bugs at
  the state-machine level** that neither tool addresses, by giving
  the LLM a way to express them as TLA+ and discharging via TLC.
- **NOT a CA / neural CA system** (yet). Our project's longer
  ambition is to formulate bug discovery as cellular-automaton
  evolution over a Solidity grammar lattice. That's the next layer;
  this paper is the substrate underneath it.

## 6. Future work

1. **Wire constrained decoding** (T8 in our internal task list) to
   close the syntactic-validity gap for smaller open models.
2. **Hybrid retrieval** (T19) to fix the embedder discrimination
   problem documented in § 4.2.
3. **Verifier-router classifier** (T4) — given a candidate lead,
   predict which verifier (Slither, Halmos, TLC, human) should
   discharge it. Routes the lead to the cheapest sufficient layer.
4. **Marginal-recall benchmark** (T5) — quantify what each verifier
   layer adds vs the previous. Publishable benchmark gap: no current
   smart-contract auditing literature reports tool head-to-head
   numbers on contest corpora.
5. **CA-over-grammar layer** — formulate FailureMode discovery as
   diffusion over the Solidity grammar lattice. Speculative but
   philosophically aligned with how bug families cluster.

## 7. Reproducibility

All code, specs, and the grammar are in
[plumbline](https://github.com/qizwiz/plumbline):

```
docs/tla/                    — 5 hand-authored FailureMode specs
                               + tla2tools.jar (TLC v2.19)
docs/tla/imported/           — 9 pact-checker FailureModes
                               (cross-domain retrieval seed)
grammar/tla_failuremode.lark — Lark CFG for the TLA+ subset
tools/spec_retrieval.py      — retrieval index (fastembed + cosine)
tools/validate_tla_grammar.py— Lark validator (5/5 PASS at commit time)
docs/CONTEST_RUNBOOK.md      — operational play for smart-contract audits
```

To reproduce the TLC discharges:

```bash
cd docs/tla
for cfg in *.cfg; do
  mod="${cfg%.cfg}"
  echo "=== $mod ==="
  java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
    -config "$cfg" -deadlock "$mod" 2>&1 | tail -15
done
```

Expected: each spec reports its named invariant violated with a
short counterexample trace.

## 8. Acknowledgments

The architecture is heavily shaped by:
- LTLGuard (arxiv 2603.05728) for the retrieval + grammar +
  constrained decoding ablation.
- The pact-standalone TLA+ corpus
  ([pact](https://github.com/qizwiz/pact)) for the convention of
  plural `INVARIANTS` / `PROPERTIES` blocks and the scalar-constant
  pattern.
- The Cyfrin smart-contract audit corpora
  ([boss-bridge](https://github.com/Cyfrin/2023-07-boss-bridge),
  [puppy-raffle](https://github.com/Cyfrin/2023-10-Puppy-Raffle),
  [sequence-v3](https://github.com/Cyfrin/2025-03-sequence-v3))
  for the ground-truth bug shapes.

---

*This document is the deliverable of plumbline task T12. It is
currently a working note — not submitted as preprint. If you would
like to discuss extension or replication, see the repository.*
