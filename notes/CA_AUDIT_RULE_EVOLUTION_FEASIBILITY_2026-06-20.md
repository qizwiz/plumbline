# Strategic Feasibility — CA + S-expression + halmos-grounded audit rule discovery

**Date:** 2026-06-20
**Generated from:** Deep-research workflow `wsbt086zx` (106 agents, 3.8M tokens, 20 min) — hit Anthropic session limits at 8:20pm CDT, killing the synthesis step and ~30 verification votes. **9 claims survived adversarial 3-vote verification** (FunSearch ×4, DreamCoder ×2, CEGIS ×2, SyGuS ×1). The synthesis below is mine, mixing those verified anchors with prior knowledge (clearly marked).

**Verdict (one line):** **Cautious go, but build the FunSearch-shape first; add the CA topology only if the simple island-model version works.**

---

## What the research run verified (high-confidence anchors)

These 9 claims passed adversarial 3-vote verification:

### FunSearch (DeepMind 2024) — the closest direct prior art
- **Evolves programs, not solutions** — substrate is executable code, LLM (PaLM 2) is the variation operator, an automated evaluator is the fitness signal, top programs return to a pool. [Source 1: deepmind.google/discover/blog/funsearch...]
- **Evaluator-as-hallucination-guard** — only programs that execute and verify are admitted to the population [Source 2, vote 2-1].
- **Produced genuinely novel mathematical discoveries** — largest known cap sets in 20 years; bin-packing algorithms beating established heuristics. Verifier-gated evolutionary program synthesis CAN surface novel results, not just rediscover.
- **Loop shape verified**: "select programs from pool → LLM creatively builds upon them → new programs auto-evaluated → best return to pool."

### DreamCoder (Ellis et al., 2020)
- **NOT a verifier-grounded approach** — wake-sleep Bayesian program learning with task-solving success + neural recognition models as the signal. Different grounding regime than halmos-grounded fitness. [Source: arxiv.org/abs/2006.08381]
- **Different shape from what we want** — it grows a learned DSL via abstraction, not a population evolving under formal-verifier judgment.

### CEGIS (Solar-Lezama, MIT)
- **Core empirical hypothesis**: for most synthesis problems, only a small set of input examples is needed to fully constrain the solution. The algorithm couples an inductive synthesizer with a separate validation procedure that supplies counterexamples. [Source: people.csail.mit.edu/asolar/papers/thesis.pdf]
- **Convergence rate**: each iteration cuts the candidate set by ~2^15. 2^600-candidate sketches converge in ~40 iterations; 2^80-candidate sketches in ~5. AES sketch found 1024 32-bit constants after only 600 candidates examined. **This is the formal grounding for "verifier-counterexample loop converges fast even for astronomical spaces."**

### SyGuS (Syntax-Guided Synthesis)
- **Formal framing**: synthesis = (semantic constraint: formula φ in theory T) ⊕ (syntactic constraint: grammar E of allowed expressions). [Source: sygus.org]
- This is the canonical academic framework for verifier-grounded synthesis. Our proposal is a population-based explorer over a SyGuS-shaped problem.

---

## My prior-knowledge additions (lower confidence, NOT 3-vote verified — workflow died before these could be checked)

I'm marking these as `[PRIOR-KNOWLEDGE]` so you know which inputs are training-data-derived vs research-anchored.

- `[PRIOR-KNOWLEDGE]` **Tierra (Tom Ray, 1991)** — assembly-language organisms competing for CPU cycles. Notable for the emergent "parasites" that exploited replication code of other organisms. Demonstrated emergent ecology from a tiny rule set. NOT verifier-grounded.
- `[PRIOR-KNOWLEDGE]` **Avida (Ofria/Lenski/Adami)** — generalized Tierra with environment-mediated fitness. Used heavily in evolutionary-biology research. Same pattern: programs competing under a fitness landscape, not a verifier.
- `[PRIOR-KNOWLEDGE]` **AlphaEvolve (DeepMind 2025)** — successor to FunSearch with broader scope, paired LLM proposer + automated evaluator, claimed novel matrix-multiplication improvements. Compute scale: not publicly disclosed in detail, but described as "weeks of compute on TPU clusters."
- `[PRIOR-KNOWLEDGE]` **Slither (Crytic/Trail of Bits)** — ships ~100 hand-written detectors. No published work on evolving detectors automatically.
- `[PRIOR-KNOWLEDGE]` **Daikon / ICE-DT / Houdini** — invariant inference for general programs (not Solidity-specific). Adjacent literature for the "evolve invariants under a verifier" frame. ICE-DT specifically uses counterexample-counterexample-implication learning — closest in spirit to what we'd build.
- `[PRIOR-KNOWLEDGE]` **No published work** on evolving Solidity audit rules under formal verifier fitness as far as I can recall. The gap in (4) of the original brief looks real.

---

## Should we build this?

**Yes, cautiously, with the smallest-working-thing version first.**

The structural shape is verified to work — FunSearch is essentially a proof-of-concept that LLM-proposes-program + verifier-as-fitness + self-improving-loop produces novel discoveries. Verified prior art (9 claims). What is novel for our use case:

| Element | Status |
|---|---|
| LLM as variation operator | ✓ Standard (FunSearch, AlphaEvolve) |
| Evaluator-as-fitness gating | ✓ Standard (FunSearch, CEGIS, SyGuS) |
| Self-improving program pool | ✓ Standard (FunSearch) |
| **S-expression representation for audit rules** | Novel — no verified prior art |
| **Halmos (symbolic execution) as the verifier** | Novel for Solidity audit-rule synthesis — no verified prior art |
| **CA spatial topology for interaction** | Novel — possibly unnecessary (see Failure Mode 5 below) |

The first three are well-trodden; the last three are the genuine gap. Building them is a real engineering question, not a research moonshot.

**The HIGHEST-EV minimum-viable shape**:
1. Start with FunSearch's shape (single pool, island-model migration, LLM proposer, automated evaluator).
2. Substitute halmos as the evaluator for Solidity audit-rule candidates.
3. Use a typed grammar over Solidity AST predicates (not raw S-expressions) for the candidate representation — biases toward syntactically-valid candidates and side-steps the flat-landscape failure mode.
4. ONLY add the CA spatial-topology layer if (1)+(2)+(3) produces useful audit rules AND you have a reason to believe spatial locality (vs island migration) gives you something. Don't build the CA part on aesthetics.

---

## Failure modes and how each manifests in our design

### 1. Verifier-as-bottleneck (HIGHEST RISK — quantifiable)
- **Halmos throughput**: 0.5-5 sec per verdict (per your prompt context). At 1 sec average:
  - Population 100 × 100 generations = 10K solves → ~3 hours
  - Population 1K × 100 generations = 100K solves → ~28 hours
  - Population 1K × 1K generations = 1M solves → ~280 hours = ~$300-1000 of Modal CPU
- **FunSearch's scale**: "weeks of compute" on TPU clusters for cap-set bounds. AlphaEvolve similar. We should expect to need MUCH more compute than the math-discovery problems because Solidity audit rules have a higher per-verdict cost than a simple math-problem evaluator.
- **Mitigation**: parallelize across Modal heavily, cache verdicts by AST-hash, use cheap pre-filters (slither / regex) to reject syntactically-invalid candidates before halmos.

### 2. Trivial-program collapse
- A vacuously-true rule (`assert true`, `assert 1==1`) will always be PROVED by halmos and dominate the population.
- **Mitigation**: SHARPNESS fitness — a rule must (a) be PROVED on a held-out clean-contract set AND (b) be REFUTED (COUNTEREXAMPLE) on a held-out known-buggy-contract set. Both required. Single direction is insufficient. This is the discriminative-vs-generative distinction.

### 3. Verifier-gaming (Goodhart's Law against halmos)
- Halmos has documented incompleteness: loop unwinding bounds, missing semantic models for certain opcodes, can produce false-PROVED on infinite-loop cases that exceed unwind budget.
- A population WILL discover S-expressions that exploit these gaps rather than express real audit properties.
- **Mitigation**: cross-verify high-fitness rules against a SECOND verifier (foundry-fuzz + slither + manual review) before promoting to the canonical population. This is the ensemble-verifier pattern.

### 4. Fitness landscape flatness
- Random S-expressions in an audit-rule grammar will mostly fail to even parse to a valid halmos property. Without gradient, you get random walk.
- **Mitigation**: typed grammar with strong typing constraints, GENERATE-from-grammar (not mutate-arbitrary-string), and seed initial population with hand-written rules. Seeding is the load-bearing trick that FunSearch uses (their "skeleton" code).

### 5. Premature CA-fetishization
- CA topology is aesthetically appealing (matches your visual intuition about S-expr morphology) but **may not buy you anything FunSearch's island model doesn't**. Spatial locality is meaningful when neighbor-distance encodes a similarity metric over candidates that the search can exploit. For audit-rule evolution, that's not obvious.
- **Mitigation**: build the simple version first; A/B test CA-vs-island; commit to CA only if it wins empirically. Per your CLAUDE.md "smallest working thing" pattern.

---

## Load-bearing design decisions

### 1. **The grammar / representation of audit rules** (most important)
Three options, ordered by how-much-fitness-landscape-shape-they-give-you:
- **(a) Halmos-property DSL** — generate Forge tests with inline `assert` claims about contract behavior. Maximally direct fit with halmos but constrained to what halmos can verify.
- **(b) Slither-detector-shaped DSL** — generate detectors over Solidity AST predicates (function-has-modifier, state-write-in-loop, etc.). Easier to write, less powerful than halmos verification.
- **(c) Hybrid invariant DSL** — generate invariants expressible in both halmos test form AND slither predicate form, dispatch to whichever verifier fits. Most flexible, most engineering.

Recommendation: **(a) first**. Sharpest verifier coupling, even if narrower expressive range. Expand to (c) only if (a) plateaus.

### 2. **What halmos returns and how it maps to fitness**
- PROVED on clean contract = +1 fitness
- COUNTEREXAMPLE on known-buggy contract = +2 fitness (this is the discriminative signal)
- TIMEOUT = -0.5 (penalize verifier-incompleteness exploitation)
- COUNTEREXAMPLE on clean contract = -1 (false positive)
- PROVED on known-buggy contract = -2 (failed to detect — most expensive error)
- Multi-objective Pareto front, NOT single scalar — this matters for the next decision.

### 3. **Pareto selection vs scalar selection**
- Single-scalar fitness (sum of above) is what most evolutionary systems use. Easy, well-understood.
- Pareto-frontier selection (NSGA-II-style) preserves diversity along the precision/recall/generality axes. Slower to converge but produces more useful end-population.
- Recommendation: **scalar with adaptive harshness FIRST** (lisp-ca's pattern), upgrade to Pareto only if convergence is too narrow.

---

## Confidence and what would change the answer

**Current confidence**: medium-high that the FunSearch-shape works for Solidity audit rules; medium that halmos throughput is sufficient at affordable scale; LOW that the CA-topology adds value above island-model.

**What would change my answer to "no, don't build"**:
1. Discover that halmos at the scale we'd need ($1K compute budget, ~100K solves) yields fewer than ~10 novel useful audit rules in a 24-hour run. That's the floor of "useful." If FunSearch-on-Solidity is below that throughput, it's not a product-grade lever.
2. Discover prior art that already did this and showed it caps at the same precision as Slither's hand-written detectors. (My prior-knowledge says no, but the workflow died before that question was deeply checked.)
3. Discover that the typed-grammar problem is much harder than expected — that authoring a grammar over Solidity AST predicates rich enough to express interesting rules takes 2+ weeks of dedicated work BEFORE the loop can even run.

**What would change my answer to "yes, build the full CA version"**:
1. Empirical evidence that spatial-locality interaction (vs island migration) recovers a class of rules that single-pool evolution misses. Without that, the CA topology is overhead.
2. Demonstrable need for the CA's "neighborhood inheritance" property — e.g. you want rules that work well on contract-shape-X to influence the rules being generated for contract-shape-Y. That's a transfer-learning argument, and the CA topology naturally supports it.

---

## Next reads (specific papers/repos worth a focused read before building)

Verified-prior anchors:
- **FunSearch** — DeepMind blog post + Nature paper. Read for: program-pool architecture, evaluator API shape, prompt engineering for the LLM-as-variator. https://deepmind.google/discover/blog/funsearch...
- **CEGIS thesis** (Solar-Lezama) — read for: the "small input set fully constrains solution" empirical claim and convergence-rate analysis. https://people.csail.mit.edu/asolar/papers/thesis.pdf
- **SyGuS spec** — read for: the canonical (semantic + syntactic constraint) formal framing that our problem reduces to. https://sygus.org

`[PRIOR-KNOWLEDGE]` worth checking but not verified by this run:
- **AlphaEvolve paper / blog** (DeepMind 2025) — successor to FunSearch with broader scope and disclosed-some compute scale.
- **DreamCoder** (Ellis et al. arxiv:2006.08381) — even though it's not a fit for our design, the wake-sleep DSL-extension idea is worth knowing about as an alternative to evolution.
- **ICE-DT** (counterexample-counterexample-implication invariant learning) — closest spirit to what we'd build for the invariant-synthesis angle.
- **Solar-Lezama's Sketch tool** — practical CEGIS implementation, possibly worth lifting libraries.
- **Slither's detector codebase** (github.com/crytic/slither) — 100 hand-written detectors as the seed population for our initial generation.

---

## Honest caveats on this report

1. **The workflow died at the synthesis step.** This report is my manual synthesis; you should treat the 9 verified claims as the only high-confidence anchors. Everything marked `[PRIOR-KNOWLEDGE]` is my training-data recall and should be spot-checked before being load-bearing in any architectural decision.

2. **~30 verification votes failed on session limits.** Claims about Slither's detector count, Halmos integration with Foundry, AlphaEvolve's compute scale, SyGuS solver envelope — none of these got the adversarial 3-vote treatment. Re-running with budget after 8:20pm CDT (session reset) would harden the report.

3. **Sourced claims are heavily FunSearch-weighted.** The workflow's search angles over-indexed on FunSearch because it's the clearest match for the question shape. A broader Tierra/Avida/Eureqa/Genetic-Programming sweep is missing — would change the failure-mode analysis if those systems hit modes our design would also hit.

4. **My recommendation hinges on halmos throughput.** If the per-verdict cost is significantly higher than 1 sec on real audit-rule candidates (compounds + admin checks + multi-contract interactions), the compute math gets uglier fast.

---

## What this report enables

This is the **strategic-feasibility** layer. Approved next step (if you go) is a **technical-design** spec — a separate document that answers the 3 load-bearing decisions above with concrete API choices, then breaks the build into 2-week milestones. Same shape as today's `RANKING_FITNESS_GATE_SPEC_2026-06-20.md` — name the thing, sketch the API, identify integration points, before writing code.

If you don't go: this report becomes the "considered, rejected, here's why" artifact that justifies focusing on other levers (proposer-level Sonnet bet, prompt-enumeration fix, accepting the 0.22 ceiling and writing up).
