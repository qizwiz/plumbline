# Is RAG the best thing for what we're trying to achieve?

Source: deep-research workflow run 2026-06-07, 107 subagents, 4.2M
tokens, 25 claims adversarially verified (13 confirmed / 12 refuted).
The high refute rate is a feature, not a bug — it kills several
"RAG is everything" claims we'd have otherwise relied on.

## Direct answer

**RAG is the right FIRST lever, not the LAST. Keep growing it. But
budget for two complementary directions, because RAG cannot reach
the bugs it just missed on sequence.**

## Why RAG works AT ALL on Solidity (verified)

Our measured +0.25-0.34 lift on sequence (0.08-0.17 → 0.42) is
**consistent with the Python/JavaScript pattern** in
[arxiv 2510.27675](https://arxiv.org/abs/2510.27675) — kNN few-shot
selection delivers measurable F1 lift on Python/JS code (Python/SVENP
Qwen 0.59→0.78; JS/NodeMedic Gemma 0.57→0.85). On C/C++, the same
paper reports "limited impact" and recommends fine-tuning as the
escalation.

**Solidity surface-form is closer to JS than C/C++** — so our lift
is expected, not a fluke.

## Why RAG cannot reach the 7/12 misses (the structural ceiling)

The deep-research finds **even fine-tuned LLMs hit a recall ceiling
of ~0.68 on hard logic bugs** (price manipulation, the closest
benchmark; [arxiv 2504.05006](https://arxiv.org/abs/2504.05006)).
The paper explicitly characterizes price manipulation as
"non-machine-auditable" with current LLM techniques.

Our missed bugs map to three distinct classes:

| miss | class | does RAG help? | does fine-tuning help? |
|------|-------|----------------|------------------------|
| H-01 flag-bypass | novel shape, no past analog | NO — index doesn't contain it | LIMITED — training data also won't have it |
| M-02 ERC-4337 caller through EntryPoint | deep semantic | NO — pattern-match doesn't penetrate | YES if examples teach it (recall ~0.5-0.7) |
| M-03 function-returns-constant | data-flow | NO — needs control-flow analysis | LIMITED — same ceiling |
| L-01 cumulative drift | execution-trace bug | NO | LIMITED — static analysis gap |

**RAG IS NOT THE WRONG TOOL FOR THE WRONG JOB. IT IS THE RIGHT TOOL
HITTING ITS STRUCTURAL CEILING.** That ceiling is roughly where we
landed (0.42).

## Two refutations that change what we'd budget for

### Vanilla multi-agent debate is overrated (REFUTED 3-0)

[Huang et al. ICLR 2024](https://arxiv.org/pdf/2310.01798) Table 4
GSM8K: at equal compute, self-consistency 9-sample reaches 88.2% vs
multi-agent debate at 83.0%. Vanilla MAD is consistency aggregation
with extra LLM costs. **At budget parity, ENSEMBLE.goal.md-style
self-consistency dominates a debate stage.**

Implication: we'd been considering panel-of-judges as a recall lever.
**Don't.** That budget should go to RAG-K-sweep or more sol_intent
samples.

### Intrinsic self-correction loops DEGRADE (REFUTED 3-0)

Same paper: GPT-3.5 on CommonSenseQA drops −37.7pp (75.8% → 38.1%)
after one self-correction round. The model biases toward
plausible-looking alternative answers regardless of correctness.

**BUT** — and this is a plumbline-specific nuance the literature
doesn't measure — the pipeline ALREADY HAS external oracles
(TLC/halmos/slither). **Self-correction WITH oracle grounding is
viable.** A "lead → TLC → if undecided, revise → retry" loop
exploits exactly the configuration where self-correction works.

This is a unique architectural advantage plumbline has that the
LLM-vulnerability-detection literature doesn't capture. Worth
documenting + leveraging.

## What the literature DOES recommend post-RAG

### Domain LoRA/QLoRA fine-tuning (CONFIRMED 3-0)

[SmartLLM](https://arxiv.org/pdf/2502.13167) uses QLoRA on LLaMA 3.1.
[iAudit ICSE 2025](https://arxiv.org/html/2403.16073v3) says verbatim:
"Fine-tuning could be a promising approach to embed Solidity-specific
vulnerability data into the model itself, compared to RAG."

**Catch**: SmartLLM/iAudit fine-tune on thousands of contracts. Our
.ANSWERS history is 49 findings. **Below ~200 findings, fine-tuning
likely overfits** (open question from research; not directly verified).

So fine-tuning is the right move ~contest 3-4 when corpus reaches
200+ findings. Not contest 1.

### Ranker-Critic justification stage (CONFIRMED 2-1)

[iAudit](https://arxiv.org/html/2403.16073v3) reports cause-explanation
consistency 24.13% (GPT-4 baseline) → 37.99% (Mixtral 8x7B
Ranker-Critic with 10-constraint prompt + agree/rerank/merge).

This is the **usable-lead rate**, not recall. For plumbline: a Ranker
that critiques each lead BEFORE TLC discharge could reduce wasted
verifier runs. Precision lift, not recall lift.

**Catch**: not validated on Claude Sonnet. Transfer is open.

### Chain-of-Thought (CONFIRMED 2-1)

"While CoT prompting often enhances precision, its impact on recall
can vary across different scenarios"
([arxiv 2502.07049](https://arxiv.org/pdf/2502.07049)). **CoT is not
a recall lever above an RAG baseline. Use for precision only.**

## The plumbline-specific decision matrix

| direction | recall lift | setup | per-run cost | compounding | contest-1 |
|-----------|-------------|-------|--------------|-------------|-----------|
| **GROW RAG corpus** | est +0.05-0.10/corpus added | trivial | $0 | YES — every new .ANSWERS row improves it | YES |
| **NEW TLA+ shapes for 3 misses** | est +0.10-0.25 (M-02 already covered by ERC4337StaticSigDoS, M-03 NOT-TLA-shaped, H-01 done tonight as FlagBypasses) | 1h/shape | $0 | YES | YES |
| **RAG K-sweep + tighter prompt** | est +0.05-0.15 | 1h | $5-10 A/B | YES (config persists) | YES |
| **Ranker-Critic on Claude Sonnet** | precision, not recall | 1-2h | +$2/lead set | YES if works | MAYBE |
| **Hybrid RAG + spec_retrieval** (inject matched TLA+ shape descriptions as few-shot) | est +0.10-0.20 (M-02 would re-surface) | 1-2h | $0 | YES | YES |
| **Self-consistency K=5** | est +0.05-0.10 | 1h | +5× LLM cost | NO (per-run) | MARGINAL |
| **Domain LoRA fine-tuning** | est +0.15-0.25 IF corpus 200+ | 1-2 days | $50-100 one-time + free inference | YES (permanent capability) | NO (corpus too small) |
| **CoT prompt addition** | 0 (recall), +precision | 30min | +tokens | YES | YES |
| **Halmos extension** | est +0.05 (conservation only) | 1+ week | $0 | YES | NO (out of contest 1 budget) |
| **Slither custom plugins** | est +0.03-0.10 per plugin | 4h/plugin | $0 | YES | YES |
| **Multi-agent debate (vanilla)** | UNDERPERFORMS self-consistency | 2h | +K× LLM cost | NO | NO |
| **Intrinsic self-correction** | DEGRADES recall per literature | 30min | +tokens | NO | NO |

## Ranked top-3 next investments

### 1. Hybrid RAG + spec_retrieval injection ($0, ~2h, contest-1 deployable)

When sol_intent runs `--rag`, ALSO call `spec_retrieval.query_top`
with the chunk text. If a TLA+ shape matches cos > 0.55, inject its
description as an ADDITIONAL few-shot example. This routes around
the failure that "M-02 has no past .ANSWERS finding RAG could match"
because **we already have an ERC4337StaticSigDoS shape** — the
mechanism IS known to the system; it just isn't in the .ANSWERS
index used by RAG.

Expected lift on sequence: M-02 should surface. Recall delta likely
+0.10-0.20.

This is the highest-leverage thing the deep-research surfaced. Goal
file pattern: HYBRID_RAG.goal.md.

### 2. Author TLA+ shape for M-03 (function-returns-constant)

The deep-research caveats: "the strongest 'RAG beats fine-tuning'
framing is NOT supported" + corpus is too small for fine-tuning. So
the contest-1 lever is **more structural coverage in the form
RAG+spec_retrieval can already exploit** (per #1).

M-03 is a data-flow bug. TLA+ models it as "two-action contract:
RealSigner returns recovered hash; BuggyImpl returns a constant.
Invariant: returned value matches recovery input." 2-state
counterexample expected. Goal file: CORPUS_GROWTH.goal.md
(template already exists).

### 3. Self-correction WITH external oracle loop ($1-5/contest, 1d wall)

The literature refutes intrinsic self-correction but DOESN'T refute
oracle-grounded self-correction. Plumbline has the oracle (TLC).
A loop like:

```
for lead in leads:
   r = tlc_discharge(lead)
   if r == "undecided" and not_yet_revised:
       new_lead = ask_claude("the verifier couldn't decide. revise...")
       continue
   else: break
```

…exploits exactly the configuration where self-correction works.
**Plumbline-specific advantage** that LLM-vulnerability literature
doesn't measure.

## Direct refutations of paths we'd have wasted budget on

| we'd have considered | why not |
|----------------------|---------|
| Multi-agent debate panel-of-judges | UNDERPERFORMS self-consistency at equal compute (Huang et al., 3-0 verified) |
| Critique-then-revise loop (no oracle) | DEGRADES recall −37.7pp (3-0 verified) |
| Fine-tuning right now | Corpus 49 findings < literature's thousands; overfit risk |
| CoT as recall lever | Precision-only (2-1 verified) |

These all looked plausible going in. The deep-research kills four
budget-wasters with citations.

## Honest caveats

1. **49-finding corpus is the bottleneck.** Most cited papers use
   1000s. Every contest grows the corpus by 5-15 findings. Plan for
   3-5 contests before fine-tuning is on the menu.

2. **Numeric transfer is fragile.** The 0.68 ceiling, the 24%→38%
   lift, the 88.2% vs 83.0% — all measured on non-Solidity
   benchmarks. The QUALITATIVE ranking transfers; the SPECIFIC
   numbers don't.

3. **Plumbline's TLA+/TLC layer is uncited.** No paper measures the
   "LLM RAG + TLA+ FailureMode discharge" combination. Our 0.83
   recall when leads are good is unique architectural evidence the
   literature doesn't have.

4. **Contest-1 expectation stays at 30-50% recall.** Even with all
   three top-3 implemented, the literature's fine-tuned ceiling on
   hard logic bugs is 0.68. **Don't promise 90%.**

## The honest answer to "is RAG the best?"

**RAG is necessary and sufficient for the pattern-class bugs in our
contest corpora. It is not sufficient for novel shapes (CORPUS_GROWTH
handles those), deep-semantic bugs (oracle-grounded self-correction
+ Ranker-Critic close some of that gap), or data-flow bugs (Halmos
extension or custom slither plugins — both out of contest-1 budget).**

The pipeline as currently designed — RAG for breadth, TLA+ shapes
for structural coverage, TLC for discharge, slither as free safety
net, hybrid router for routing — is **architecturally correct**.
The investment is in growing each layer, not replacing any of them.

**Tonight measured: RAG +0.25-0.34 lift is real.** Stop here, ship,
contest 1, learn from contest 1's gaps, then come back and decide
which of the top-3 to invest in based on what actually missed in
contest 1.
