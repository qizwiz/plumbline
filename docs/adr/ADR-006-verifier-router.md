# ADR-006: Reframe ml_classifier as Verifier-Router

**Status**: Design accepted, implementation pending (T4)
**Date**: 2026-06-06
**Author**: plumbline session (overnight T4)
**Related**: ADR-004 TLA+ as semantic layer; ARCHITECTURE.md §3a→§3b shift

## Context

The current `tools/ml_zoo.py` trains a **binary classifier** on
`(lead, label)` pairs where `label ∈ {real, noise}`. It's a real
classifier (4-way sweep, GradientBoosting wins at ROC-AUC ≈ 0.80
± 0.15), but the framing is wrong.

The **Steenhoek et al. ICSE 2023** result on GNN vulnerability
detection — F1=0.5 cross-dataset — is the canonical warning. A
binary "real-vs-noise" classifier optimizes for the wrong thing:
**OOD recall**. On a new contest, the previous bug distribution
doesn't transfer. The classifier confidently mislabels.

What we actually need is a **router**: given a lead, predict which
**verifier** is best positioned to discharge it. The verifier itself
gives the soundness verdict; the router gives only a cheap routing
decision. A misrouted lead costs a wasted verifier run; a
misclassified one costs a missed bug.

Per CLAUDE.md "the AI proposes, a formally-verified gate disposes":
the classifier should NEVER decide truth, only **work allocation**.

## Decision

Reframe `ml_classifier` from a binary `{real, noise}` head to a
**multi-class router** with the following label set:

```
{
  slither_will_catch,    // syntactic-pattern bug, slither is cheap+sufficient
  halmos_will_decide,    // conservation/invariant bug, halmos handles
  tlc_will_decide,       // state-machine bug, TLA+ FailureMode + TLC handles
  human_only,            // novel logic / domain assumption / spec gap
}
```

Each class has a **distinct downstream cost** and **distinct
verifier surface**. The router's job is to send the lead to the
cheapest sufficient layer.

### Label rules (from the existing 41-rep dataset)

Manual relabeling pass over `reps.jsonl`:

| Pattern in lead | Label |
|-----------------|-------|
| reentrancy + named CEI / external-call ordering | `slither_will_catch` (slither has a checker for this) |
| `tx.origin` / `delegatecall` / `selfdestruct` patterns | `slither_will_catch` |
| arithmetic overflow + Solidity ≤ 0.7.x | `slither_will_catch` |
| conservation: balance, total supply, total fees | `halmos_will_decide` |
| protocol invariant on accounting | `halmos_will_decide` |
| should-be-one-shot patterns (replay, reentrancy via state machine) | `tlc_will_decide` |
| msg.sender misread / caller-bound auth across paths | `tlc_will_decide` |
| idempotency / non-deterministic dispatch | `tlc_will_decide` |
| narrow-accumulator truncation | `tlc_will_decide` (Uint64FeeOverflow shape) |
| oracle staleness | `human_only` (domain assumption) |
| game-theoretic incentive | `human_only` |
| spec is unclear / scope-bound assumption | `human_only` |

### Routing policy

```
def route(lead: str) -> list[str]:
    """
    Returns ordered list of verifiers to try.

    The order encodes cost: slither is free, halmos costs gas,
    TLC costs human-author time for new specs, human-only is
    the most expensive.

    The router predicts MULTIPLE classes via softmax; we try
    them in order of predicted probability until one discharges
    or all fail. Last resort = human_only.
    """
    probs = classifier.predict_proba(lead)
    routes = sorted(zip(LABELS, probs), key=lambda x: -x[1])

    # Always include slither at minimum confidence — it's free
    if routes[0][0] != "slither_will_catch":
        routes.append(("slither_will_catch", 0.0))

    # Drop verifiers below threshold to avoid wasted runs
    return [r for r, p in routes if p > 0.10 or r == "slither_will_catch"]
```

### Architectural distinction from a "confidence classifier"

A traditional bug-finder classifier outputs `confidence ∈ [0, 1]`
that the lead is a real bug. We DO NOT output that — we output a
**routing distribution**, and the verifier(s) give the truth.

The router can be **uncalibrated and still correct**. If it
mis-routes 30% of leads to `slither_will_catch`, the cost is one
free slither run; the lead then routes to its actual verifier. The
DOWNSTREAM PIPELINE has the verifier soundness; the router only
trades runs for cost.

This is the same reason real ML systems separate **retrieval**
(loose, fast, recall-oriented) from **re-ranking** (tight, expensive,
precision-oriented): the routing layer's job is to expand the
candidate set, not to decide truth.

## Consequences

### Pros
- **Robust to OOD.** On a new contest, even if the router's predicted
  probabilities are calibration-off, the verifier-pipeline still
  handles the routing decision soundly.
- **Cheap.** Routing is a single forward pass; the cost is whichever
  verifier(s) actually run.
- **Composable.** Each verifier remains independently sound. The
  router only changes ALLOCATION of runs.
- **Honest under failure.** If all routed verifiers fail, the route
  lands at `human_only` — explicit escalation, not silent confidence.

### Cons
- **Labels are scarce.** Our 41-rep dataset doesn't have explicit
  verifier-routing labels. The relabeling pass per the table above
  requires ~1 hour of manual work; we have it lined up but not done.
- **Classifier choice may differ.** The current 4-way sweep
  (GradientBoosting winner) was tuned for binary ROC-AUC. The multi-
  class sweep may pick a different winner (likely still
  GradientBoosting given tabular nature, but verify).
- **Router prediction errors LEAK into wasted runs.** If router puts
  a `tlc_will_decide` lead first into halmos, halmos will report
  "cannot decide" and waste ~30s. Mitigation: use the predicted
  probability threshold (default 0.10) to prune low-probability
  verifiers.

### Open questions
- **Multi-label vs single-label per lead.** Some leads genuinely
  benefit from BOTH halmos and TLC discharge (defense-in-depth). The
  routing policy above supports this (softmax > threshold returns
  multiple), but the LABEL SET assumes one-best. Revisit if we
  observe many ambiguous leads in practice.
- **Should the router predict the FailureMode within `tlc_will_decide`?**
  E.g. route to `SignatureReplay` vs `ReentrancyDrain`. Currently
  delegated to `spec_retrieval.py`; the router only decides
  verifier-class. Cleaner separation, but doubles the model count.

## Implementation sketch

1. **Schema change** (`reps.jsonl`):
   - Add `verifier_route: ['slither' | 'halmos' | 'tlc' | 'human']`
     to each rep — a list, not a single value, since defense-in-depth
     leads have multiple
   - Add `verifier_outcome: dict[str, 'discharged' | 'undecided' | 'wrong' | null]`
   - Existing `label: 'real' | 'noise'` stays — describes the bug-existence
     ground truth, not the routing decision

2. **Relabel script** (`tools/relabel_for_router.py`, ~50 LOC):
   - Walk `reps.jsonl`
   - Apply the table-rules above as a deterministic-classifier baseline
   - For ambiguous leads, leave `verifier_route: null` for manual review
   - Write `reps_routed.jsonl` (don't mutate the original — append-only
     contract from CLAUDE.md)

3. **Multi-class trainer** (`tools/ml_zoo_router.py`, fork of `ml_zoo.py`):
   - Same feature stack (embedding + engineered) as current `ml_zoo`
   - Multi-class targets from the relabel step
   - 5-fold stratified CV
   - Per-class precision/recall, NOT just ROC-AUC
   - Save `tools/router_classifier.pkl`

4. **Inference** (`tools/route_lead.py`, ~30 LOC):
   - Load `router_classifier.pkl`
   - Take a lead from stdin or argv
   - Print routing decision: ordered list of verifiers with predicted
     probability

5. **Pipeline wire-up** (deferred until T15 measures actual marginal
   recall — we need ground truth before we can score router accuracy):
   - `sol_intent` → `route_lead` → run verifiers in order → log outcome

## Validation plan

Run the router on the 41-rep dataset; measure:
- **Top-1 accuracy** vs the relabeled ground truth
- **Top-1-OR-top-2 accuracy** (the policy tries the top 2 by default)
- **Cost** (number of verifier runs per lead, vs all-verifiers baseline)

Acceptance threshold: top-2 accuracy ≥ 85% on hold-out, with
average cost ≤ 1.5 verifier runs per lead (vs 4.0 for run-all
baseline). If we miss either, the router framing is wrong or
the labels are too noisy.

## What this ADR explicitly does not commit to

- A particular ML model (the existing 4-way sweep choses GradientBoosting;
  the multi-class sweep may differ)
- An online-learning loop. The router is retrained from the rep log;
  it does not update mid-contest. Stability beats marginal accuracy
  during the contest window.
- A confidence calibration. The router outputs ordering; calibration
  (does p=0.7 mean 70% of those leads route correctly?) is nice to
  have but not blocking.

---

*Decision: implement in this order — schema change → relabel script →
multi-class trainer → inference → wire-up.* Steps 1-4 are
self-contained and can be done before any contest. Step 5 waits on
T15 marginal-recall data.
