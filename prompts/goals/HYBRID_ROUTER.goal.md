Between-contest goal: close the tlc-routing gap from ROUTER_TRAIN
(tlc F1 = 0.08) by composing spec_retrieval as a pre-check ahead of
the ML router. Per ROUTER_CAVEATS.md "Option 3 (hybrid)". $0 LLM
spend; ~20-30 LOC. <4000 chars; 8-step.

---

For the existing verifier-router (route_lead.py), add a hybrid layer:
if any TLA+ shape from docs/tla/ matches the lead with cos > THRESHOLD,
return tlc_will_decide as primary BEFORE falling through to the ML
classifier. Validate that "signature accepted twice no nonce" — which
ROUTER_TRAIN routed to slither+halmos — now routes to tlc.

DONE WHEN ALL EIGHT HOLD:

1. tools/route_lead_hybrid.py exists, ≤60 LOC. Imports
   spec_retrieval + route_lead. Has a single function
   `route(lead: str, threshold=0.55) -> list[tuple[str, float]]`.

2. The function first calls spec_retrieval.query(lead, top_k=1). If
   the top match has cos > threshold, returns
   [('tlc_will_decide', cos), <ML top-k except tlc>]. Otherwise
   delegates entirely to route_lead's existing logic.

3. My transcript shows the validation test:
   `echo "signature accepted twice no nonce" | python tools/route_lead_hybrid.py`
   returns tlc_will_decide as primary, with the cos score and the
   matched FailureMode name (e.g. SignatureReplay).

4. Negative test: my transcript shows
   `echo "owner can set fee address to zero" | python tools/route_lead_hybrid.py`
   does NOT route to tlc (no TLA+ shape match), falls through to the
   ML router, which routes to slither.

5. Three additional test cases printed, each showing route + reason:
   - "cross-wallet signature replay without domain binding" → tlc
     (CrossWalletSigReplay match)
   - "balance equals total supply invariant" → halmos
   - "oracle returns stale price after long block" → slither + halmos
     (ML fallback; honest about not catching human_only)

6. tools/ROUTER_CAVEATS.md updated with a new section "Hybrid router
   implemented" showing before/after for the signature-replay lead.
   The old caveat about tlc F1=0.08 remains (it's still true for the
   pure ML router) but is now bridged by the hybrid layer.

7. validate_reps.py still passes; no new reps written this goal (the
   hybrid layer is inference-only).

8. `git push origin main` succeeded; git log shows ≥1 commit
   touching tools/route_lead_hybrid.py and tools/ROUTER_CAVEATS.md.
   (Cloud loop NOT required — paths filter excludes tools/.)

CONSTRAINTS:

- $0 LLM spend. spec_retrieval is local fastembed; route_lead is
  local sklearn. No anthropic/openai calls.
- Don't modify route_lead.py or ml_zoo_router.py — the hybrid wraps
  them, not replaces them. The ML router stays as the cheap fallback.
- Don't retrain the classifier. Don't rewrite the relabeler.
- Threshold default = 0.55 (per CORPUS_GROWTH precedent — that's
  the cos at which retrieval consistently surfaces a real match).
  If 0.55 is too lax / strict, surface; do NOT silently tune.
- Keep the hybrid module ≤60 LOC. Spirit: composition, not
  reimplementation.

OPERATING DISCIPLINE:

- The TLC path is FREE in router cost terms (we already authored
  the spec; only TLC discharge time at use-time). So adding it as
  primary routes correctly without inflating avg_cost.
- The hybrid layer NEVER suppresses the ML router — it prepends tlc
  when it matches. Slither still appears as the free safety net.
- Self-critique at step 5: are the test cases meaningfully different
  bug-classes, or am I cherry-picking lookups I know will match?

OUT OF SCOPE:

- Pipeline wire-up to sol_intent → hybrid_router → verifier (T15+).
- Improving sol_intent recall (RECALL_PROMPT.goal.md).
- Authoring new TLA+ shapes (CORPUS_GROWTH.goal.md).
- Tuning the cos threshold via grid search (between-contest if
  observed misroutes warrant it; not this goal).

If spec_retrieval.query fails to import (fastembed install gap) or
the test on "signature accepted twice no nonce" returns cos < 0.55,
surface — the assumption that "tlc shapes are retrievable at the
default threshold" was tonight's working hypothesis, and a measured
counterexample is honest signal not failure.
