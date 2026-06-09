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

> **Seed paragraph (JH expand from here):**
>
> Smart-contract auditing has converged on a quality standard for proof
> of concept: a runnable Foundry test that reproduces the vulnerability
> against a forked or locally-deployed target. Sherlock, Code4rena, and
> Immunefi all require it; prose-only submissions are auto-rejected or
> down-judged. Yet the *path* from "a TLA+ specification of a structural
> bug class violates its invariant" to "a Foundry test that reproduces
> the bug on a specific contract" is currently a hand-coded step — every
> shape and every target needs its own bespoke test scaffold. This paper
> describes plumbline, a pipeline that closes that gap with a single
> universal Foundry test template plus per-target JSON manifests. The
> universal template plus a manifest plus a lint-and-emit tool reduces
> the TLA+-to-PoC step from ~3 hours of hand-coding per (shape, target)
> pair to ~10 minutes of JSON authoring with static + dynamic verification.

*[JH next: expand the motivation. Cover:*
- *Why verifier-discharge as a frame: LLM proposes, verifier disposes*
- *The "elite human auditor + tooling" gap that plumbline tries to close*
- *Why the universal template + JSON manifest beats per-shape Jinja templates*
- *Reference: docs/research/IMMUNEFI_STRATEGY.md*
*]*

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

## 7. Conclusion

*[JH: ~3 sentences. The verifier-discharge frame, the universal-template
generalization, what's measurably better since adopting this.]*

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
| 2026-06-09 | 1 | Outline + Section 1 seed | ~250 | Scaffolded by Claude; JH to expand |
