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

**The problem.** Smart-contract auditing has converged on a quality standard for proof of concept: a runnable Foundry test that reproduces the vulnerability against a forked or locally-deployed target. Sherlock, Code4rena, and Immunefi all require it; prose-only submissions are auto-rejected or down-judged. Yet the path from "a TLA+ specification of a structural bug class violates its invariant" to "a Foundry test that reproduces the bug on a specific contract" is currently a hand-coded step — every shape and every target needs its own bespoke test scaffold. The bookkeeping is significant: imports, role grants, pragma matching, prank lifetimes, replay sequencing, invariant assertions. Each (shape, target) pair takes ~3 hours of focused engineering, and most of that time is spent re-discovering the same authoring footguns rather than thinking about the bug.

**The trust question that shapes the architecture.** LLMs are fluent in any technical language they have training data for, including TLA+ and Solidity, but they also lie — confidently, in syntactically-valid form, in ways a non-expert reader cannot easily detect. For a solo auditor whose submissions get judged by adversarial reviewers, an LLM that produces a syntactically-clean-but-semantically-wrong specification is worse than no LLM at all. The architectural question was therefore: *what is the shape of engineering truth that lets one actually depend on a model's output?* The answer adopted here is **verifier discharge** — the LLM proposes; a sound checker disposes. The LLM proposes a TLA+ shape, but TLC's invariant check either violates the property (a real counterexample trace) or does not (the spec is too weak). The LLM proposes a Foundry test, but forge either reproduces the exploit on a deployed target or does not. The model is allowed to be wrong; the verifier is not. Soundness moves out of the language model and into the discharge tool.

**This paper's contribution.** We describe plumbline, a pipeline that closes the TLA+-counterexample-to-Foundry-PoC gap with a single universal Foundry test template plus per-target JSON manifests, plus a lint-and-emit tool. The universal template plus a manifest plus the lint reduces the TLA+-to-PoC step from ~3 hours of hand-coding per (shape, target) pair to ~10 minutes of JSON authoring with static + dynamic verification, measured end-to-end on two case studies (Section 3). We also catalog the recurring authoring footguns the lint catches at commit time (Section 4) and report the limitations of the current implementation honestly (Section 5).

**Division of labor.** The pipeline is built on a specific three-way pairing: shape-recognition is the human's job, fluency is the LLM's job, soundness is the verifier's job. A human auditor working alone can recognize the structural shape of a vulnerability — *"this looks like first-depositor inflation," "this looks like signature replay"* — but converting that recognition into a well-formed TLA+ specification or a runnable Foundry test is high-friction symbolic work. An LLM working alone is fluent in TLA+ and Solidity syntax but has no reliable taste for which abstraction matches the actual bug; left to itself it produces specifications that compile but model the wrong thing. The verifier (TLC for the spec, forge for the PoC) is sound but mute — it tells you yes or no, not what to write next. Plumbline pairs them: the human provides the shape, the LLM provides the fluency, the verifier discharges the result. The contribution of this paper is the specific glue that makes this three-way pairing tractable for smart-contract auditing.

The motivation just described is local — the trust question forced the verifier-discharge frame, which forced the universal-template + manifest pipeline. There is a longer-running research program in which this work sits — broadly, the structural-hypothesis claim that software engineering's missing intrinsic ground truth can be recovered by lifting more engineering work into mechanically-discharged structural transformations. We treat that program as future work in Section 7 to keep the present paper anchored in what is built and verified.

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

**Target.** dreUSDs is an ERC-4626 vault with the standard `_virtualBalance` mitigation against direct-transfer share-inflation attacks. The mitigation tracks deposits + claimed rewards in a state variable; subsequent share-price calculations use `_virtualBalance` rather than the raw asset balance, so an attacker depositing 1 wei then donating tokens directly to the contract cannot inflate the share-price.

**The structural gap.** `totalAssets()` is implemented as `_virtualBalance + rewardsDistributor.vestedAmount()`. The vested-amount channel grows over real time *without touching `_virtualBalance`*. An attacker who deposits 1 wei first, then waits for the admin to add rewards and for time to pass, sees `totalAssets()` climb without `_virtualBalance` changing. A subsequent victim deposit computes `shares = depositAmount * totalSupply / totalAssets`; with `totalSupply = 1` and `totalAssets` inflated by the vested amount, the victim's share count rounds toward zero. Both redeem; the attacker captures a disproportionate fraction of the combined `_virtualBalance + vested`.

The bug is the same family as classic first-depositor inflation, but the inflation channel is the *documented mitigation's own dependency contract*, not a direct token transfer. The `_virtualBalance` mitigation is silently bypassed because no one wrote down the structural invariant *"all state changes affecting share-price must flow through `_virtualBalance`"* — the vested-rewards channel is an auxiliary path no one tagged as share-price-relevant.

**How the bug was actually found (honest pathway).** Plumbline's structural-cascade clustering (`tools/mine_contest.py`) embedded the 157 DRE functions against a corpus of 1,191 prior Code4rena findings, ranking each function by nearest-neighbor cosine similarity to past bug descriptions. The top 20 surfaced (with their highest-cosine prior match):

- #1 `dreRewardsDistributor._claimVested` (cos 0.84) ← *"AuraVault::claim reward calculation does not deduct fees from reward amount, causing DoS"*
- #2 `dreOVaultComposer._redeemAndSend` (cos 0.83) ← *"`AuraVault::redeem` calculation error"*
- #4 `dreUSDs._claimVestedRewards` (cos 0.81) ← same AuraVault::claim prior
- #16 `dreUSDs._withdraw` (cos 0.80) ← *"`Share 1:1 Conversion`: if vault incurs a loss, the last user to withdraw..."*
- #20 `dreRewardsDistributor.vestedAmount` (cos 0.80) ← *"`_vested()` claimable amount calculation error"*

The cluster ranking correctly surfaced the contracts that contain the bug's components — dreRewardsDistributor (the vested channel) and dreUSDs (the share-price calculation). It did NOT surface the specific functions where the bug *manifests* (`_deposit`, `_convertToShares`). The bug emerges from the *interaction* between the contracts, not from any single function.

Manual inspection of the top-20 list (with LLM-assisted synthesis) identified the structural pattern: vested rewards in `totalAssets()` bypass the `_virtualBalance` mitigation. A TLA+ shape was then authored (`docs/tla/PausedDistributorPricingAsymmetry.tla` for the related M-1 case; the H-1 case used direct PoC authoring), and a Foundry proof-of-concept was constructed reproducing the inflation arithmetic. Sherlock submission verified the bug at HIGH severity (format-validated by the contest bot; awaiting final judging).

**Plumbline's contribution to this finding, measured honestly.** A blind cold-test of plumbline's `sol_intent` LLM-direct proposer on the full DRE codebase (Anthropic Sonnet 4.5 via OpenRouter, single run, June 9 2026) was conducted to disambiguate plumbline's automated contribution from the human-in-the-loop. The cold-test result: `sol_intent` examined 16 NatSpec promises across dreUSDManager, dreShareOFT, dreOVaultComposer, and dreRewardsDistributor and reported **zero violations**, explicitly noting *"no implementation provided"* for the relevant internal functions. The first-depositor inflation hypothesis was never proposed.

We therefore attribute the finding pathway as follows:

| Stage | Plumbline contribution | Notes |
|---|---|---|
| Scope narrowing | ✅ 7.8× search reduction (157 → top-20 candidates) | NN-cos 0.79-0.84 against the 1,191-finding corpus |
| Structural pattern surfacing | ✅ Correct contracts in top 20 | Both dreRewardsDistributor and dreUSDs surfaced |
| Bug hypothesis proposal | ❌ Sol_intent did not propose this hypothesis cold | Sol_intent's intent-vs-implementation model is text-based; the bug is a structural-invariant violation across two contracts and not anchored in any NatSpec promise |
| PoC authoring + verification | ✅ Foundry test reproducing inflation arithmetic | Built from the synthesis, not derived automatically |

The honest claim: **plumbline narrowed the haystack 7.8×; the needle was found by human reading of the top-ranked candidates with LLM-assisted synthesis.** This is a real contribution — search-space reduction at this ratio over a 50K-LOC codebase is genuinely useful for an organized solo auditor — but it is not autonomous bug identification. Section 5 (Limitations) discusses the architectural seam in the current pipeline that prevents the proposer stage from carrying the cluster-rank's structural signal forward as a hypothesis; Section 7 (H8) names this as the next-build hypothesis to test.

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
generalization, what's measurably better since adopting this. Write last,
after Sections 2-5 are filled in.]*

### 7.1 Testable hypotheses

The present work suggests several hypotheses that are out of scope to evaluate here but whose experimental tests can be specified precisely. We state them as falsifiable claims with concrete tests, not as results.

**Hypothesis H1 (the dimension-adder claim).** Each independent verifier in a structural pipeline functions as a *dimension adder* — a transformation that lifts a contract's representation into a higher-dimensional space where bug-class boundaries become more linearly separable. The current implementation realizes four such dimensions: AST (tree-sitter Solidity parsing), control-flow graph (networkx), structural-similarity embedding (BGE-small over a corpus of past findings), and temporal evolution (TLA+ traces). We hypothesize that adding a fifth — path-condition discharge via halmos / SMT — will improve bug-class separability by a measurable margin. **Proposed test:** integrate halmos as a downstream stage after the universal-template emission; on a held-out set of N≥30 contest findings, measure top-1 and top-5 NN-classification accuracy of bug-class shape before vs after halmos discharge augments the feature vector. Falsified if the improvement is within noise on a paired test.

**Hypothesis H2 (the trivialization claim).** With sufficient independent dimensions added in sequence, smart-contract auditing becomes near-trivial in the sense that bug-class detection collapses to a high-confidence nearest-neighbor lookup with rare manual intervention. **Proposed test:** define a precision/recall scoring against a frozen corpus of Sherlock-judged findings; measure how each added dimension shifts the precision/recall curve; H2 is supported if the marginal contribution of each dimension follows a saturating curve approaching ~1.0 precision at recall meaningful for contest participation (say recall ≥ 0.5).

**Hypothesis H3 (the shape/fluency/soundness factoring is correct).** The three-way pairing — human=shape, LLM=fluency, verifier=soundness — is the right factoring of audit work in the verifier-discharged frame. **Proposed test:** compare end-to-end audit yield (validated findings per hour) across (a) human alone, (b) human + LLM no verifier, (c) human + verifier no LLM, (d) full pipeline. Falsified if condition (d) is not significantly better than the maximum of (a)–(c).

**Hypothesis H8 (corpus-prior-informed structural proposer).** The current pipeline has an architectural seam at the proposer stage: structural-cascade clustering produces nearest-neighbor matches between candidate functions and corpus bug descriptions, but the proposer (`sol_intent`) ignores the NN-rank's structural signal and falls back to intent-vs-implementation text comparison against NatSpec promises. Section 3.1 reports the cold-test result: sol_intent failed to surface the DRE first-depositor inflation hypothesis on independent invocation. We hypothesize that a *corpus-prior-informed* proposer — one that ingests `(candidate function AST, matched corpus shape, the structural invariant violated in the matched prior)` and emits a structural-invariant hypothesis carrying the prior's bug class forward — would surface the bug from the same cluster-rank input. **Proposed test:** build the structural proposer (likely composed of pact's `invariant_agent.py` structural-invariant generator + corpus-prior conditioning), re-run on DRE without human intervention, and measure whether the first-depositor inflation hypothesis is proposed within the top-N leads. Test extends to other Sherlock-judged contests at scale via `c4_ingest.py`'s 1,191-finding corpus. Falsified if the structural proposer's cold-test recall on Sherlock contests does not exceed sol_intent's by a measurable margin (≥ 0.2 recall delta at fixed precision).

### 7.2 The larger program (position-paper scope)

Plumbline operationalizes one small slice of a longer-running research program around *computational material* — the conjecture that the right computational substrate for verifiable software is not a token stream but a graph-shaped object with physical properties (plasticity, attractor basins, topological invariants), and that arbitrary systems can be stitched together from physically-grounded structural components whose composition preserves truth. The smart-contract-auditing instance presented here is among the easiest cases: bug classes are well-categorized, the verifiers (TLC, forge) are mature, and the "physical substrate" is the EVM, which is finite-state enough to fit inside a discharge tool. Open questions for the larger program — including how to extend verifier-discharged structural pipelines to substrates without bounded state (general distributed systems, ML training loops), how to compose multiple verifiers whose individual soundness guarantees do not trivially compose, and whether the shape/fluency/soundness factoring is the right one or whether fluency can itself be lifted into structural form — are deferred to a separate position paper. We mention the larger program here so the reader can locate the present work in its intellectual lineage; we do not claim the present paper advances it beyond the existence-proof that the verifier-discharged pairing is tractable in at least one non-trivial domain.

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
