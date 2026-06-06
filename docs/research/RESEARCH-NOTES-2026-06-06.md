# Research synthesis — 2026-06-06 (deep-research workflow, 23/25 claims verified)

Raw data: `deep-research-2026-06-06-raw.json` (workflow output, 31 sources,
6 angles, 144 candidate claims → 25 selected → 23 verified, 2 refuted).

This note distills what changes about plumbline's architecture given the
state of art. Read alongside `ARCHITECTURE.md` and `CLAUDE.md`.

## TL;DR

1. **LTLGuard (arxiv 2603.05728) is the closest published precedent** to
   what we're building. A 7-14B open model + grammar-constrained
   decoding + retrieval-augmented few-shot reaches **75-78% semantic
   accuracy** on LTL — without fine-tuning. **Read it Saturday morning
   before authoring more TLA+.**
2. **The "prosthesis not prompting" rule we wrote into CLAUDE.md is
   empirically backed.** Few-shot and CoT consistently *degrade*
   semantic accuracy on formal-spec generation. Two refuted claims
   (self-repair @ 25%, fine-tuning closing the gap to 671B) cut the
   same direction.
3. **GNN bug-finders collapse out-of-distribution.** Our ARCHITECTURE
   §3a needs to be sharpened: the NCA-as-bug-finder must do
   **verifier-routing**, not primary bug-prediction, or we recapitulate
   the failure mode the literature already documents.
4. **Two gaps in the verified literature = two publishable directions
   for plumbline**: smart-contract tool head-to-head measurement on
   identical scopes, and a working Solidity→TLA+ pipeline.

---

## What the literature confirms about the architecture

### LTLGuard pipeline → directly applicable

**Source**: LTLGuard, arxiv 2603.05728 (Mar 2026; v1 preprint, single
benchmark; treat as plausible-but-unreplicated).

**Numbers measured**:
- Mistral-7B syntactic validity: V1 (vanilla) 10.0% → V7 (full pipeline) 92.8%
- Semantic correctness: V1 7.1% → V6 40.0% / V7 38.5%
- Qwen2.5-14B on nl2spec "hard" (36 instances): **100% syntactic validity, 75.0–77.8% semantic accuracy**
- Vs T5 fine-tuned: 5.5%
- Vs Bloom-176B nl2spec: 13.8%
- Vs Codex interactive: 86.1% (ceiling)

**Pipeline ingredients**:
- SynCode-precomputed DFA mask store (grammar constraint)
- Retrieval-augmented few-shot (nearest LTL examples as context)
- Parser feedback (treat invalid spec as gradient)

**Why it matters for plumbline**: this IS the architecture we
described in CLAUDE.md's "superpower" + ARCHITECTURE.md §3b
fluency-teacher. Replace LTL with TLA+ and the pipeline transfers
straightforwardly. The 75-78% number on a hard benchmark, with a
14B open model, is the realistic ceiling we should be aiming for.

### Prompting techniques hurt — measured, refuted, both

**Sources**: SysMBench arxiv 2508.03215, FormalBench arxiv 2503.04779.

| Enhancement | Measured effect |
|---|---|
| Few-shot | Claude 3 SysM-R: 56% → 47% |
| CoT | Claude 3 SysM-R: 56% → 43% |
| Grammar prompting | BLEU 2.6% → 10.2% but SysM-P 70% → 57% |
| **Refuted**: "self-repair gives ~25% boost" | 0-3 adversarial vote |
| **Refuted**: "FT 7-8B closes gap to 671B" | 0-3 adversarial vote |

**Implication for plumbline**: every time I reach for "smarter prompting"
on a TLA+ generation step, I'm reaching for a measured *anti-pattern*.
The correct move is grammar mask + retrieval + verifier feedback. The
prosthesis, not the prose.

### Grammar-constrained decoding: production-ready infrastructure, target-grammar gap

**Sources**: XGrammar arxiv 2411.15100 (MLSys 2025), llguidance README.

| Tool | Latency | Grammar support | Where deployed |
|---|---|---|---|
| XGrammar | ~100x speedup vs prior on CFG | Arbitrary CFG | vLLM, SGLang, TensorRT-LLM, MLC-LLM |
| llguidance | ~50μs/token mask on 128k vocab; <1% over 1ms on JSON Schema Bench | Lark CFG + embedded JSON/regex | guidance-ai stack |
| SynCode | (LTLGuard's choice) | DFA over CFG | research code |

**Critical gap**: zero published benchmarks on Lean / Coq / TLA+ /
SMT-LIB grammars. Only LTLGuard demonstrates the off-the-shelf path
for any formal-method grammar (LTL). **This is integration
engineering, not research** — but **measuring it on TLA+ would be a
publishable benchmark contribution.**

---

## What the literature warns us about

### GNN vulnerability detectors fail out-of-distribution — sharply

**Sources**: Steenhoek arxiv 2212.08109 ICSE 2023; "From Lab to
Reality" arxiv 2512.10485.

| Model + train→test | F1 collapse |
|---|---|
| LineVul trained on Juliet → ICVul | 38.77 (paper-reported was ~95) |
| ReVeal trained on BigVul → Devign | **0.5** |
| GPT-4o on May-2025 Linux CVEs | 96.24% whole-file accuracy, **F1=0** |
| VentiVul function-pair discrimination (before/after fix) | ReVeal 0/25, LineVul 3/25, GPT-4o 5/25 |
| Inter-model agreement on test examples | only ~22% across 5 transformers |

**The pattern**: in-distribution numbers look great. Cross-dataset and
real-world novel CVEs reduce to noise. This is what plumbline's NCA-as-
bug-finder layer would do *too* if built as the literature suggests.

**Updated framing for ARCHITECTURE §3a**: the NCA's job is **predicting
verifier success**, not predicting bugs. Given a lead from sol_intent
or slither, the NCA predicts *which verifier will discharge it
successfully*. That routing problem doesn't have the OOD collapse
because the verifiers themselves are sound regardless of which lead
we route to them.

### Self-reported smart-contract GNN numbers come with caveats

**Sources**: MCR-VD (Applied Soft Computing 2025, DOI 10.1016/j.asoc.2025.113435);
ANGEL arxiv 2412.10164 (Dec 2024).

- MCR-VD: F1=92.7%, acc=94.1% on SmartBugs Curated + SolidiFI + Clean
  Smart Contracts. **Caveat**: SolidiFI uses synthetic AST-template
  injection — known to inflate pattern-style detector metrics. No
  third-party Code4rena/Sherlock replication.
- ANGEL: 34.27–161.93% accuracy improvement over AMPLE on large
  graphs (>300 nodes). **Caveat**: same lack of contest-data
  replication.

**Implication**: don't trust self-reported GNN smart-contract numbers as
the floor for sol_intent + halmos + TLA+. Measure on Code4rena
directly. Tonight's 0.604 ± 0.08 sequence recall, while small-sample, is
honest because the answer key is the Code4rena report.

---

## Two gaps = two publishable directions

The workflow's verified evidence set has **no measurements** of:

1. **Slither / aderyn / mythril / halmos / certora / semgrep-sol head-to-head**
   on identical scopes, vs human auditor recall on the same scope. If
   plumbline runs the comparison on the 5 corpora we curated tonight,
   that's a publishable benchmark contribution: first head-to-head
   measurement with human and tool ground truth tied to canonical
   Cyfrin / Code4rena reports.

2. **Solidity → TLA+ pipeline** — VeriSol, K-Framework, Solidity
   SMTChecker, Certora Prover, LLM-driven approaches. Nothing surfaced
   in the verified claim set. Tonight's `SignatureReplay.tla` +
   TLC-verified counterexample matching `.ANSWERS.md` H-3 is, to our
   knowledge, **the first LLM-authored TLA+ FailureMode for a Solidity
   bug**, mechanically discharged. Scaling this to ~25 modules across
   5 corpora produces both a contest tool AND an arxiv-shaped result.

These are not pivots away from the contest. They're the same work
documented carefully.

---

## What changes about Saturday

1. **Read LTLGuard (arxiv 2603.05728) first.** Specifically Tables 1-3
   and the SynCode integration pattern. Don't author more TLA+ until
   I understand their few-shot retrieval prompt structure — it's the
   closest precedent and the lift comes from the retrieval, not the
   model.

2. **Update ARCHITECTURE §3a wording.** NCA is verifier-router, not
   bug-classifier. The OOD collapse in DL bug-finders is the
   literature's loudest warning and we should heed it.

3. **Wire XGrammar or llguidance into TLA+ generation.** Lark grammar
   for TLA+ exists (in the tlaplus VS Code extension). Constrained
   decoding turns my first-pass fluency from "lucky on bug classes I've
   seen" into "structurally correct by construction." Engineering, not
   research.

4. **Set the lofty target honestly**: matching LTLGuard's 75-78%
   semantic accuracy on TLA+ for Solidity bug classes, with a 14B-class
   open model + retrieval over pact's 12 + plumbline's growing corpus.
   That's the realistic ceiling. Anything above is upside.

---

## Caveats from the workflow itself

- LTLGuard is single-paper, v1 preprint, self-reported on one
  benchmark. Reproduce-before-trust.
- MCR-VD and ANGEL numbers are paper-author self-reported.
- XGrammar's "100x" is CFG-best; JSON-Schema is ~3x.
- Threads (4) and (5) are underrepresented in the verified set —
  absence of evidence ≠ evidence of absence.
- 2 of 25 candidate claims were refuted by 3-vote adversarial
  verification. Both refutations point the same direction as the
  architecture (prosthesis > prompting).
