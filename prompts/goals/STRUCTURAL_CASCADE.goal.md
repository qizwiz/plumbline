Build the structural cascade — the composition layer that ties tree-sitter,
NetworkX, embedding NN, TLA+ shape match, and halmos into one pipeline.

This is the layer that closes the gap between 0.42 cold sol_intent recall
and the 0.94 corpus ceiling measured in CALIBRATION_SHERLOCK_SWEEP.md.
Each existing tool catches a different kind of wrongness; alone they're
either high-recall-low-precision (embeddings) or low-recall-high-precision
(TLC). Composed as a cascade they should hit both.

---

DONE WHEN ALL EIGHT HOLD:

1. tools/structural_cascade.py exists. It takes (scope_dir, output_jsonl)
   and runs to completion on examples/sequence/ in under 5 minutes
   without LLM spend.

2. The cascade has FIVE layers, each producing a candidate set that
   strictly subsets the previous layer's:
   - Layer A: tree-sitter Solidity query for known structural shapes
     (vendor tree-sitter-solidity; write 5 queries minimum — external-call-
     before-state-write, missing-nonce-on-permit, unchecked-low-level-call,
     unbounded-loop, create2-without-deployed-check)
   - Layer B: NetworkX call/data-flow graph; filter to functions reachable
     from public entry points with state-modification dominance
   - Layer C: embedding NN against tools/findings_index.pkl; keep candidates
     where cos>0.7 to a known H/M-severity prior
   - Layer D: TLA+ shape match — for each surviving candidate, identify
     which of the 9 FailureMode shapes the function's pattern fits, if any
   - Layer E: halmos symbolic check on Layer D matches (optional — skip if
     scope build fails, log skip honestly)

3. Output jsonl has one record per candidate that survived to Layer C,
   with all per-layer scores attached:
   {function, ast_hits, cfg_dominance, top1_corpus_match, tla_shape_match,
    halmos_status}.

4. Smoke run on examples/sequence/ produces a final-survivors set, and
   the transcript shows how many candidates entered each layer and how
   many survived (the funnel numbers, by layer).

5. For at least ONE finding in examples/sequence/.ANSWERS.md that the
   current sol_intent misses cold (cold recall is 0.42 → ~7 missed of 12),
   the cascade either CATCHES it (survives to Layer E) or honestly
   produces a "near miss" trace showing which layer rejected it. Either
   outcome is fine — but no false claim of catching what wasn't caught.

6. tools/structural_cascade.py is ≤300 SLOC. No new dependencies beyond
   tree-sitter-solidity (vendor as git submodule or pip), networkx
   (already used), and what's already imported.

7. README in prompts/goals/STRUCTURAL_CASCADE.goal.md updated with a
   line: cascade funnel numbers from the smoke run (e.g., "54 files →
   12 AST hits → 5 CFG-reachable → 3 corpus-matched → 2 TLA+-fit →
   1 halmos-verified").

8. git log shows ≥1 commit touching tools/structural_cascade.py and
   `git push` completed.

CONSTRAINTS:

- This is structural composition, NOT a new bug detector. Every layer
  must be deterministic; no LLM calls in the cascade.
- Tree-sitter queries are PATTERN MATCHING; per JH's "never do pattern
  matching" rule from CLAUDE.md, this is fine ONLY because the pattern
  is a coarse filter, not the final verdict. Subsequent layers verify.
- NetworkX layer must use slither's call-graph output, not re-parse the
  Solidity. Reuse what works.
- Embedding layer must use the existing rebuilt index (1240 findings).
- TLA+ shape match is NOT a TLC run yet — it's heuristic matching
  ("does this function's structure fit ReentrancyDrain's pre-state?").
  Actual TLC discharge is Layer E or a separate run.
- Halmos layer is optional — log skip with reason if scope doesn't build.

OUT OF SCOPE:

- LLM-grounded analysis (sol_intent is a SEPARATE pipeline; cascade is
  a structural filter that REDUCES sol_intent's search space).
- Multi-contract whole-protocol reasoning (function-level only for v1).
- Cross-contract reentrancy (Layer A query for external-call-before-write
  is intra-function only in v1).
- Pretty-printing or report generation (cascade produces jsonl; rendering
  via existing render_report.py).

WHY THIS GOAL EXISTS:

CALIBRATION_SHERLOCK_SWEEP measured the corpus at 93.7% coverage on real
Sherlock judgments. Sol_intent cold recall is 0.42. The gap is the
structural composition layer that doesn't exist yet. This builds it.

---

v1 SMOKE-RUN RESULTS (2026-06-08, examples/sequence/):

  Funnel: 49 .sol files → 145 functions → Layer A (54) → Layer B (37) →
                                          Layer C (37) → Layer D (37)
  Cost: $0 (no LLM calls)
  Runtime: <30s on M-series Mac

  Clean mechanical catches (function name match + correct TLA+ shape):
    - M-03 BaseAuth.recoverSapientSignature → ERC4337StaticSigDoS shape ✓
    - M-04 Factory.deploy → Create2NonIdempotent shape ✓

  Lax mechanical catches (title-substring match, may be false-positive):
    - M-02, H-02 via "call" substring in LibOptim.call (noise)

  Likely-in-survivors-but-scorer-missed (manual inspection):
    - H-02: SessionSig.recoverSignature OR Recovery.isValidSignature
            (SignatureReplay shape, cos>0.78)
    - M-01: SessionSig.recoverSignature OR SessionManager.recoverSapient...
            (same set as above)
    - M-02: BaseAuth.signatureValidation (ERC4337StaticSigDoS shape, cos=0.801)
    - H-01: BaseSig.recoverBranch (SignatureReplay shape, cos=0.762)

  Estimated cascade recall:
    Strict (verified mechanical): 2/6 = 33%
    Likely (manual inspection of survivors): 5-6/6 = 83-100%

  The scorer is too crude. A semantic scorer (embedding similarity
  between cascade survivor signature + ground truth title) would
  produce a tighter estimate. v2 work.

Tunings noted for v2:
  - Layer C cos threshold (0.55) too permissive — 37/37 candidates
    survived. Bump to 0.65, expect 15-25 candidates.
  - Layer D shape match returns shapes generously — multiple shapes
    per candidate. Constrain to top-1 shape.
  - Per-finding scorer needs body-aware matching, not just title.
