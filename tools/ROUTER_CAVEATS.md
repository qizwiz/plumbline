# Router caveats — honest gap statement

ADR-006 acceptance gate (top-2 ≥ 0.85 AND avg cost ≤ 1.5) PASSES mechanically:
- top-2 = **0.983**
- avg cost = **0.789**

But the per-class breakdown reveals the gate passed on a biased label
distribution rather than genuine multi-class skill:

| class                 | training samples | F1  |
|-----------------------|------------------|-----|
| slither_will_catch    | 510              | 0.93|
| halmos_will_decide    | 134              | 0.82|
| tlc_will_decide       | 19               | 0.08|
| human_only            | 0                | 0.00|

The router is essentially a **slither classifier** that occasionally
predicts halmos. It does not meaningfully predict tlc or human_only.

## Concrete evidence

`echo "signature accepted twice no nonce" | python tools/route_lead.py`
returns `slither (0.48), halmos (0.43)`. The structurally-correct route
per ADR-006 is `tlc_will_decide` (replay / one-shot pattern). The router
missed it because it never saw enough tlc examples.

## What this means

The router PASSES the acceptance gate but does NOT yet meet ADR-006's
spirit: routing leads to the cheapest sufficient verifier. Slither is
"sufficient" for the leads it can catch, but tlc-shape leads will
mis-route to slither/halmos and waste the runs before falling through
to manual escalation.

In practice, for contest day:
- slither suggestions: probably correct ~93% of the time
- halmos suggestions: probably correct ~82% of the time  
- tlc suggestions: **don't trust the router for tlc** — use spec_retrieval
  similarity (cos > 0.55) directly as the tlc gate
- human_only: the router will never suggest this — escalation is purely
  "no verifier discharged" not "router said human_only"

## Why this happened

The `relabel_for_router.py` deterministic rules use keyword patterns to
assign cheapest-sufficient routes. The keyword catalog has many
slither-pattern words (reentrancy, delegatecall, tx.origin, overflow) so
slither matches first on most leads. tlc patterns (replay, idempotency,
caller-bound) are narrower; human_only patterns (oracle staleness, game-
theoretic) are even narrower and rarely appear verbatim in lead text.

## What's needed to fix

Three options for between-contest work:

1. **More labeled rows.** The data set has 663 leads → if we run sol_intent
   on the 4 remaining contest corpora (puppy-raffle, t-swap, thunder-loan,
   damn-vulnerable-defi), the rep count would roughly double, and tlc
   examples should grow proportionally with the corpus.

2. **Manual relabel pass.** ADR-006 acknowledged this risk: "Labels are
   scarce. Our 41-rep dataset doesn't have explicit verifier-routing
   labels. The relabeling pass per the table above requires ~1 hour of
   manual work; we have it lined up but not done." A manual review of the
   `verifier_route=[]` rows (7 rows ambiguous) + the 510 slither-routed
   rows would likely surface ~50 tlc and ~10 human_only.

3. **Hybrid router (pre-filter then classify).** Use `spec_retrieval.py`
   to check if any TLA+ shape matches with cos > 0.55. If yes, route tlc
   directly; otherwise fall through to the ML router. This bypasses the
   ML's bias on tlc-shape leads.

## Recommendation

**Option 3 is the cleanest near-term move** because it composes with
what we have, costs no LLM dollars, and the failure mode is benign (if
spec_retrieval misses, the ML router still suggests slither + halmos —
no worse than current).

Implementation: ~20 LOC wrapper around `route_lead.py` that calls
`spec_retrieval.query` first. Out of scope for this goal (ROUTER_TRAIN
implements the trainer + CLI; pipeline wire-up is T15+ per ADR §step 5).

## Acceptance gate verdict

The gate is honored: top-2 0.983, cost 0.789. But the gate measures
top-2 ACCURACY, not per-class UTILITY. We did not lower the bar — we
hit a bar that turned out to measure the wrong thing on this data.

Logging this as a known limitation so that future work doesn't claim
the router is "validated" when it's really "validated for the
slither-dominant lead distribution we have."
