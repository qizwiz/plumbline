# From TLA+ Counterexample to Foundry Exploit: A Verifier-Discharged Pipeline for Smart-Contract Auditing

**Jonathan F. Hill** (jonathan.f.hill@gmail.com)
**Draft:** 2026-06-09 — target arXiv submission 2026-06-15

---

## Abstract

*[Write last. ~150 words. State: what the pipeline does, the
verifier-discharge insight, the case studies, the precision/recall numbers
from reps.jsonl, the limitations.]*

---

## 1. Motivation

The pipeline is the latest test of a longer-running hypothesis: that software engineering's hardest problem is the absence of intrinsic ground truth. Unlike mechanical or civil engineering, where gravity, material strength, and dimensional tolerance enforce a baseline of reality that cannot be argued away, software is words about words. A program that compiles is not a program that works; a test that passes is not a proof of correctness; a specification that reads well is not one that has been checked. We have long held that the only place ground truth lives in software is in its *structure* — the AST, the call graph, the type lattice, the proof tree, the cellular automaton — and that the right system architecture is one that lifts as much engineering work as possible into structural transformations whose correctness can be mechanically discharged.

The hypothesis has a corollary: the right computational substrate is not a token stream but a *graph* — a thing with positions, edges, neighborhoods, and topology. Internally we call this *computational material*: a substrate that computes but also has physics — plasticity, attractor basins, properties that survive under composition. The motivating image is the McDonald-brothers' tennis-court scene from *The Founder*, in which two engineers optimize a kitchen workflow by walking it with chalk on asphalt: machine learning made physical, gradient descent enacted by two humans on a parking lot. The conjecture this paper does not prove but is shaped by is that arbitrary systems can be stitched together from physically-grounded structural components, and the truth of their composition follows mechanically from the truth of their parts. Plumbline is a small instance of this larger program; the program itself is left to a separate position paper (Section 7).

The local question that motivated plumbline was about trust. LLMs are fluent in any technical language they have training data for, including TLA+ and Solidity, but they also lie — confidently, in syntactically-valid form, in ways a non-expert reader cannot easily detect. For a solo auditor whose submissions get judged by adversarial reviewers, an LLM that produces a syntactically-clean-but-semantically-wrong specification is worse than no LLM at all. The architectural question was therefore: *what is the shape of engineering truth that lets one actually depend on a model's output?* The answer, in this domain, is verifier discharge — the LLM proposes a TLA+ shape, but TLC's invariant check either violates the property (a real counterexample) or doesn't (the spec is too weak). The LLM proposes a Foundry test, but forge either reproduces the exploit or doesn't. The model is allowed to be wrong; the verifier is not. Soundness moves out of the language model and into the discharge tool.

Concretely, smart-contract auditing has converged on a quality standard for proof of concept: a runnable Foundry test that reproduces the vulnerability against a forked or locally-deployed target. Sherlock, Code4rena, and Immunefi all require it; prose-only submissions are auto-rejected or down-judged. Yet the *path* from "a TLA+ specification of a structural bug class violates its invariant" to "a Foundry test that reproduces the bug on a specific contract" is currently a hand-coded step — every shape and every target needs its own bespoke test scaffold. This paper describes plumbline, a pipeline that closes that gap with a single universal Foundry test template plus per-target JSON manifests. The universal template plus a manifest plus a lint-and-emit tool reduces the TLA+-to-PoC step from ~3 hours of hand-coding per (shape, target) pair to ~10 minutes of JSON authoring with static + dynamic verification.

The pipeline is built on a specific division of labor: shape-recognition is the human's job, fluency is the LLM's job, soundness is the verifier's job. A human auditor working alone can recognize the structural shape of a vulnerability — "this looks like first-depositor inflation," "this looks like signature replay" — but converting that recognition into a well-formed TLA+ specification or a runnable Foundry test is high-friction symbolic work. An LLM working alone is fluent in TLA+ and Solidity syntax but has no reliable taste for which abstraction matches the actual bug; left to itself it produces specifications that compile but model the wrong thing. The verifier (TLC for the spec, forge for the PoC) is sound but mute — it tells you yes or no, not what to write next. Plumbline pairs them: the human provides the shape, the LLM provides the fluency, the verifier discharges the result. The contribution of this paper is the specific glue that makes this three-way pairing tractable for smart-contract auditing — a universal Foundry template, per-target JSON manifests, and a lint that catches the recurring authoring footguns before they cost real session time.

---

## 2. Pipeline Architecture

*[Diagram needed: 5-stage flow.]*

Stages:
1. **Shape authoring (manual or LLM-assisted).** TLA+ specification of a
   bug class. INVARIANT statement names the property the buggy contract
   violates.
2. **Counterexample discharge.** TLC with deadlock-off finds a violation
   trace within ~6 states for typical bug shapes.
3. **Target manifest (JSON).** Per-target manifest binds the shape to a
   concrete contract: target path, contract name, pragma, setup block,
   trace replay block, invariant assertion block, extra imports.
4. **Universal template emission.** `tools/trace_to_forge.py` substitutes
   manifest fields into `templates/foundry_poc/_universal.t.sol.template`,
   producing a Foundry `.t.sol` file.
5. **Lint + run.** `tools/manifest_lint.py` static-checks for known
   footguns (Section 4) and optionally runs forge against the emitted
   test, reporting pass/fail.

*[JH expand: each stage gets ~3-4 sentences. Reference the actual files.]*

---

## 3. Case Studies

### 3.1 Sherlock 1259, Issue #1 — First-Depositor Inflation via Vested-Rewards Channel

*[JH: write this. You did this work. Source: runs/2026-06-08-dre-structural/SHERLOCK_SUBMISSION.md
+ corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd/test/PoC_FirstDepositorInflation*.t.sol
Cover:*
- *The contract: dreUSDs ERC-4626 vault with _virtualBalance mitigation*
- *The structural gap: vested-rewards channel bypasses the mitigation*
- *The cluster-guided discovery (corpus NN ranked the vulnerable function)*
- *The PoC: Alice with 1 wei + admin adds rewards → victim deposits get rounded to 0*
- *Severity / Sherlock submission status*
*]*

### 3.2 Sherlock 1259, Issue #2 — Paused-Distributor Pricing Asymmetry

*[JH: source: runs/2026-06-08-dre-structural/SHERLOCK_SUBMISSION_M1.md
+ docs/tla/PausedDistributorPricingAsymmetry.tla
+ tools/manifests/dre-PausedDistributorPricingAsymmetry.json
Cover:*
- *The TLA+ INVARIANT statement (ShareValuePreserved)*
- *The counterexample trace (6 states; pause leaves vested in totalAssets but blocks claim)*
- *The manifest → Universal_PausedDistributor.t.sol → forge PASS*
- *Alice extracts 75 dreUSD on 50 deposit; Bob reverts.*
*]*

---

## 4. Footgun Catalog

Each entry below cost real session time and now has a static check in
`tools/manifest_lint.py`.

### 4.1 vm.prank consumption by argument-expression calls

*[JH: write this. Source: CLAUDE.md "Foundry vm.prank footgun" section.
The DRE M-1 manifest hit this for 30 minutes today. Lint catches it now.]*

### 4.2 Pragma drift between target and template

*[JH: ^0.8.20 emitted against a 0.7.6 puppy-raffle target. Caught by
forge compile, but lint flags pragma mismatch earlier.]*

### 4.3 Missing extra_imports for non-default Solidity types

*[JH: ERC1967Proxy, IERC20, EndpointV2Mock — every M-1 PoC needs these.
Initially the universal template had no extra-imports slot. Now it does.]*

### 4.4 forge_root resolution

*[JH: short. Manifests should declare it explicitly; the fallback heuristic
is slow + lossy.]*

---

## 5. Limitations

*[JH: be honest. Cover:*
- *Verifier-discharge is only as honest as the TLA+ abstraction. If the
  spec models the wrong thing, the forge PASS proves the wrong thing.*
- *LLM authoring of TLA+ shapes is fluency-shaped, not soundness-shaped.
  Most generated specs fail to TLC-violate on the first try; iteration
  costs real time. Memory of the FirstDepositorInflation cycle: spec
  written but invariant did not violate → NULL-HONEST.*
- *Precision/recall numbers from reps.jsonl with confidence intervals.
  *[INSERT REAL NUMBERS: total reps, validated, gauntlet-rejected, etc.]**
- *Universal template covers ERC-4626 patterns + simple reentrancy +
  signature replay. Doesn't cover cross-contract callback graphs,
  multi-transaction sandwich patterns, or anything requiring symbolic
  execution of unbounded state.*
*]*

---

## 6. Related Work

*[JH: cite, briefly. ~half page max.]*
- **Halmos** (a16z) — symbolic execution for Foundry tests. Plumbline
  leans on Foundry as the discharge runtime; Halmos integration is future
  work, not in scope.
- **Slither** (Trail of Bits) — static analyzer for Solidity. Plumbline
  uses slither output as a leads source upstream of TLA+ specification.
- **TraceFix** (arXiv 2605.07935) — TLA+ counterexample to JavaScript
  trace repair. Methodologically similar; different target language.
- **LTLGuard** (arXiv 2603.05728) — constrained decoding for LTL
  specification generation. Plumbline's TLA+ shape authoring would
  benefit from this; not yet integrated.
- **Cyfrin Updraft** — security curriculum. Not a tool but the dominant
  training pipeline; this paper's audience overlaps with Updraft's
  graduates.

---

## 7. Conclusion and Future Work

*[JH: ~3 sentences on the verifier-discharge frame, the universal-template
generalization, what's measurably better since adopting this.]*

### Future Work — the larger program

Plumbline operationalizes one small slice of a longer-running research
program around *computational material* — the conjecture that arbitrary
software systems can be stitched together from physically-grounded
structural components and that the truth of their composition follows
mechanically from the truth of their parts. The smart-contract-auditing
instance presented here is the easiest case: the bug classes are
well-categorized, the verifiers (TLC, forge) are mature, and the
"physical substrate" is the EVM, which is finite-state enough to fit
inside a discharge tool. Open questions for the larger program include:
how to extend verifier-discharged structural pipelines to substrates
without bounded state (general distributed systems, ML training loops);
how to compose multiple verifiers whose individual soundness guarantees
don't trivially compose; whether the "shape-recognition + fluency +
soundness" three-way pairing is the right factoring or whether the
fluency role can itself be lifted into structural form. We expect to
treat these in a separate position paper; the present work is the
existence proof that the pairing is tractable in at least one
non-trivial domain.

---

## References

*[Build as you write the sections. Include arXiv links.]*

---

## Submission notes

- **Venue:** arXiv cs.SE primary, cs.CR secondary.
- **License:** CC-BY-4.0 (allows commercial use, requires attribution).
- **LaTeX template:** start from arXiv's generic template; markdown
  conversion via pandoc with `--natbib` at submission time.
- **Code release:** point to qizwiz/plumbline (after the divergence with
  origin is resolved — see open loop).
- **Author affiliation:** Independent researcher (or "Plumbline" as
  org-of-one if preferred).

---

## Daily progress log (append-only, mirror CURRICULUM.md)

| Date | Day | Section worked | Word count | Notes |
|------|-----|----------------|------------|-------|
| 2026-06-09 | 1 | Outline + Section 1 motivation (5 paragraphs) + Section 7 future-work note | ~900 | Interview mode: JH directed shape, Claude transcribed. Captures structural-hypothesis → computational-material → AI-lying / verifier-discharge → tool description → shape/fluency/soundness division of labor. |
