# Design sketch: `tools/structural_proposer.py`

**Status:** design only. NOT to be built during the 18-day arXiv-paper window. This is the H8 follow-up build, scoped here so the paper's Section 7 H8 claim is concrete-and-testable rather than vague.

**Authored:** 2026-06-09 (Day 1 of curriculum, after the sol_intent cold-test on DRE returned ZERO violations)

---

## Problem statement (from Section 3.1 + Section 7 H8)

Plumbline's current pipeline has two distinct sub-systems stapled together:

- **Structural narrowing** (`tools/structural_cascade.py` + `tools/mine_contest.py`): tree-sitter AST → CFG → embedding NN ranking against the 1,240-finding corpus → per-candidate `corpus_top1/top3` (matched prior bugs) + `tla_top1_shape` (matched TLA+ failure mode). This is pure structural-hypothesis machinery.
- **LLM-text proposal** (`sol_intent.py`): reads README / NatSpec / source text, hunts for intent-vs-implementation contradictions. This is text-comparison machinery on a different hypothesis.

**The seam:** structural narrowing produces a rich object per candidate function with the matched corpus prior + the matched TLA+ shape + the halmos status field, but **nothing consumes that information** to author a structural-invariant check. The proposer stage ignores the structural signal and falls back to sol_intent's text comparison. On DRE this failed: sol_intent solo returned zero violations and did not propose the first-depositor inflation hypothesis the cluster rank had structurally surfaced.

## Architectural sketch

Add one module, `tools/structural_proposer.py`. Compose with existing infrastructure rather than re-build.

```
cascade.jsonl entry                pact's invariant_agent _propose_prompt
─────────────────────              ─────────────────────────────────────
{                                  - LLM proposes invariants from 5
  "function": "_deposit",            categories (conservation, solvency,
  "contract": "dreUSDs",             monotonicity, authorization,
  "text": "...",                     no-overflow)
  "corpus_top1": {                 - Emits halmos check_*.sol test
    "id": "M-19",                  - Halmos discharges
    "title": "Share 1:1
      Conversion vault loss…"      [no prior conditioning, no shape input]
  },
  "tla_top1_shape":
    "OracleStaleness",
  "corpus_top1_cos": 0.80,
  "halmos_status": null
}
        │
        ▼
   structural_proposer.propose_check(entry, corpus_invariants, tla_shapes)
        │
        ▼
   halmos check_* test parameterized by:
     - target function's source (from entry.text)
     - matched prior bug's STRUCTURAL INVARIANT (from corpus annotation pass)
     - matched TLA+ shape's INVARIANT statement (from docs/tla/<shape>.tla)
        │
        ▼
   pact's halmos_check.run_halmos() → verdict (proved / violated + counterexample)
        │
        ▼
   gauntlet.adversarial_verify(verdict) → STRONG / WEAK / REJECT
        │
        ▼
   write to reps.jsonl with proposer="structural"
```

## The corpus-annotation pre-pass (Pass A)

**Current corpus state** (verified by reading `tools/findings_index.pkl`):

```python
{
  "findings": [        # length 1240
    {"id": "M-07",
     "title": "`PrizeVault.maxDeposit()` doesn't take into account produced fees",
     "source": "c4",
     "corpus": "2024-03-pooltogether",
     "severity": "M"},
    ...
  ],
  "embeddings": ndarray(1240, dim),
  "embedding_dim": int
}
```

**What's missing:** no `structural_invariant` field per finding. The invariant the prior bug violated is implicit in the title prose only.

**Pass A — one-time corpus annotation:**

1. For each of the 1,240 findings, ask the LLM (`anthropic/claude-sonnet-4-5`) to extract the structural invariant the bug violates, framed as a halmos-shaped property. Example transformations:

   | Prior title | Extracted structural invariant |
   |---|---|
   | "`AuraVault::claim` reward calculation does not deduct fees" | `conservation: assert(claimed + reservedFees == grossReward)` |
   | "Share 1:1 Conversion: if vault incurs a loss, last withdrawer..." | `monotonicity_of_share_price: assert(sharePrice(t+1) >= sharePrice(t))` |
   | "`PrizeVault.maxDeposit()` doesn't take into account produced fees" | `conservation: assert(maxDeposit == cap - currentAssets - producedFees)` |
   | "First-depositor inflation via direct transfer" | `mitigation_channel_monotonicity: assert(totalAssets == virtualBalance)` |

2. Add `findings[i].structural_invariant` field. Re-pickle.

3. Validate by sampling 50 findings and confirming the extracted invariants are halmos-compilable (or near-compilable).

**Cost estimate:** 1240 findings × ~500 tokens prompt × $3/Mtok input ≈ $1.85 per pass. Plus ~200 tokens output × $15/Mtok ≈ $3.72. Total ≈ $5-6 for Pass A. Acceptable.

**Effort:** 4-6 hours (script + validation + iterate prompt).

## The structural_proposer (Pass B)

**Interface:**

```python
def propose_check(
    cascade_entry: dict,           # one row from cascade.jsonl
    corpus_findings: list[dict],   # annotated by Pass A
    tla_shapes_dir: Path,          # docs/tla/
) -> str:
    """Emit a Halmos check_*.sol test source.

    Reads:
      cascade_entry.text             — target function source
      cascade_entry.corpus_top1.id   — matched prior's structural_invariant
      cascade_entry.tla_top1_shape   — matched TLA+ shape's INVARIANT statement

    Returns:
      Solidity test contract source. Pact's halmos_check.run_halmos() can
      discharge directly; no glue code needed beyond writing the file and
      passing the foundry root.
    """
```

**Prompt skeleton (adapted from pact's `_propose_prompt`):**

```
You are a smart-contract auditor using symbolic execution (Halmos).

PRIOR BUG MATCHED: <corpus_top1.title>
PRIOR BUG'S STRUCTURAL INVARIANT (violated in the matched contest):
  <corpus_top1.structural_invariant>

TLA+ FAILURE MODE MATCHED: <tla_top1_shape>
TLA+ INVARIANT STATEMENT:
  <extracted from docs/tla/<shape>.tla>

TARGET FUNCTION: <contract>.<function>
TARGET SOURCE:
  <cascade_entry.text>

PROPOSE: a Halmos `check_*` test that asks whether this target function
violates the SAME structural invariant the matched prior violated. Don't
propose generic invariants — be specific to this prior + this shape.

[remaining prompt structure from pact's _propose_prompt — emit
ONE invariants contract with one or more check_<name>(<args>) functions,
SPDX/pragma boilerplate, etc.]
```

**Composition with existing infrastructure:**

- Write emitted source to a temp foundry project.
- Call `halmos_check.run_halmos(root)` → verdict list.
- Pass each verdict to `gauntlet.py` for adversarial validation.
- Append rep to `reps.jsonl` with `proposer={"kind": "structural", ...}`.

**Effort:** 6-8 hours (prompt iteration + integration + testing on DRE + on the existing 4 Cyfrin benchmarks).

## Validation experiment for H8

**Hypothesis (from Section 7 H8):** A corpus-prior-informed structural proposer surfaces the DRE first-depositor inflation hypothesis from the same cluster-rank input on which sol_intent returned zero violations.

**Procedure:**
1. Run Pass A on the corpus (one-time).
2. Implement `tools/structural_proposer.py`.
3. Re-run `mine_contest.py` on DRE to regenerate cascade.jsonl.
4. For each of the top-20 cascade entries, run `structural_proposer.propose_check` + halmos discharge.
5. Score the resulting leads against Sherlock #1's answer key.
6. Compare:
   - sol_intent solo recall on DRE: **0** (measured 2026-06-09)
   - structural_proposer recall on DRE: ?
   - structural_proposer recall on the 4 Cyfrin benchmark corpora vs sol_intent: ?

**Falsification criterion:** structural_proposer's recall delta over sol_intent on this corpus must exceed 0.2 at fixed precision. If not, H8 is falsified and the proposer-stage redesign needs a different shape.

## Open questions before building

1. **Are the matched TLA+ shapes' INVARIANT statements halmos-compatible?** TLA+ INVARIANT is over a state machine; halmos `assert` is over an EVM execution path. The translation isn't always direct. May need a per-shape "halmos translation" hint in the TLA+ comment header.

2. **Does pact's invariant_agent's `Invariants` contract structure (single test contract, multiple check_* methods) compose cleanly with the per-cascade-entry granularity?** Plumbline emits one cascade row per function; pact emits one invariants contract per contract. May need batching (one invariants contract aggregating all relevant check_* from a contract's candidate functions) for efficiency.

3. **Does the existing `cascade.jsonl` `halmos_status` field already attempt this composition partially?** Worth tracing what writes that field and what it expects there.

4. **Corpus-annotation prompt — how robust?** The structural-invariant extraction is doing a non-trivial NLP-to-formal translation. Some prior findings have title prose that doesn't cleanly map to a halmos invariant (e.g., "smart contract winners halt the raffle"). Either the extraction tags such findings as "no clean structural invariant available" or we accept a noise floor.

5. **Cost at scale.** If contest-day uses this proposer end-to-end, what's the per-contest API cost? Pass B per cascade entry is probably ~$0.10. With ~150 entries per contest after filtering, that's ~$15 per full contest mine. Acceptable if precision improves.

## Effort summary

| Stage | Effort | Cost | Risk |
|---|---|---|---|
| Pass A (corpus annotation) | 4-6 hours | $5-6 API | Low — straightforward LLM batch |
| `structural_proposer.py` core | 6-8 hours | <$1 dev | Medium — prompt iteration |
| H8 validation experiment (DRE + 4 benchmarks) | 4-6 hours | $5-15 API | High — could falsify |
| **Total** | **14-20 hours** | **$15-25** | **Acceptable** |

This is a real follow-up. It fits in a focused week sometime after the arXiv paper ships.

## Why this design is honest

- It does NOT pretend the gap is small; the corpus-annotation pre-pass is real work.
- It does NOT pretend H8 is guaranteed; falsification criterion is concrete.
- It does NOT propose merging plumbline and pact wholesale; surgical composition at the proposer seam only.
- It DOES name the open questions that could derail the build, before they show up at runtime.

## REVISED 2026-06-09 EVENING — curvature framing exposes a deeper problem

Day 1 evening: ran Pass A skeleton + N=50 sample run with adversarial REFUTE-default validator. Result: 7/50 CLEAN (14%), 43/50 REFUTED. Calibration test showed the validator was correctly catching even hand-authored "good" invariants for known bugs.

**JH surfaced the deeper framing** (which I missed initially): the 14% CLEAN rate may not be a prompt-quality issue. It may be a **representation-dimensionality** issue. The 9-category taxonomy in `pass_a_spec.json` expects single boolean assertions over current state — a 1D, scalar, algebraic representation. But many real bugs live on **curved manifolds**:

- **Reentrancy** is a trajectory in (state × call-depth) space — temporal, not single-state
- **First-depositor inflation** is a hyperbolic relation `share_price = totalAssets / totalSupply` — relational, not algebraic
- **Signature replay** is a cardinality constraint `count_of_uses(msg) ≤ 1` — counting, not predicate
- **MEV / front-running** is a hyperproperty over multi-transaction orderings — multi-trajectory

A flat boolean assertion collapses curved spaces to flat predicates. The information loss explains the validator's high refute rate: even "good" extractions are subtly wrong because the representation is fundamentally too lossy.

**Implication for the structural_proposer redesign:**

Pass A should produce **multi-mode** structural invariants:
- `scalar_check` (current) — single boolean over current state → halmos check_* single function
- `relational_constraint` — algebraic relation between 2+ state variables → halmos check_* with multiple state snapshots
- `temporal_invariant` — sequence of state assertions across actions → halmos targetContract + invariant_*
- `counting_invariant` — cardinality bound over a domain → ghost variable + halmos
- `manifold_constraint` — region in state space → TLA+ INVARIANT + TLC discharge

Each mode routes to a different discharge backend in Pass B. The current architecture assumed one backend (halmos check_*); the redesign needs to route by mode.

**The curvature-research-swarm Workflow is in flight** (launched 2026-06-09 evening). Returns synthesis containing:
- Honest verdict: is curvature framing novel / supported / refuted by the literature?
- Concrete redesigned JSON schema for Pass A
- Mode-to-backend mapping table
- Migration plan with time estimates
- Yes/no call on whether to attempt this redesign before Day-5 cutoff
- Section 7 H12 framing (testable hypothesis)

**Tomorrow morning's first task** (regardless of swarm result):
- JH reads the swarm synthesis
- If swarm says GO: implement the multi-mode schema, regenerate Pass A spec, re-run sample, target ≥40% CLEAN (lower threshold acknowledges representational diversity)
- If swarm says NO-GO: accept 14% CLEAN, restrict Pass B to scalar-extractable findings only, document as Section 7 limitation
- Either way, the curvature framing goes in Section 7 as either H12 (new hypothesis) or as limitation discussion

---

## Discipline boundary

**This file is design, not build.** Building begins after:
1. arXiv paper posted (target: 2026-06-15).
2. SHSU endorsement secured + first reader feedback received.
3. Sherlock 1259 judging complete (whatever direction the result).

Earliest realistic build window: late June 2026. The 18-day curriculum's hard rule against new architecture projects still applies.
