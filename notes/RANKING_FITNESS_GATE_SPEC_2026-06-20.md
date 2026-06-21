# Ranking-Fitness-Gate Spec — the missing self-falsifier

**Date:** 2026-06-20
**Status:** spec only — names the primitive, defines API, identifies integration points. Build is ~1 day after this spec lands.
**Motivation:** today (2026-06-20) a 14-agent diagnostic synthesizer recommended two empirical fixes (dedupe-at-K + dataflow-distance signal). Both turned out to be wrong. They were caught manually with a $0 simulator (`tools/h14_lift_simulator.py`). If the loop had been driving today's decisions without me as the falsifier, it would have spent ~$30-50 of Modal on the wrong bet.

**Per `~/.claude/CLAUDE.md`:**
> Don't improve-then-intervene — build the STRUCTURE for self-improvement. When something fails, the instinct is to diagnose and hand-fix it yourself. Resist. Build the grounded, correctly-attributed self-improvement loop and let the SYSTEM fix its own components.

Today was improve-then-intervene. This spec names the missing structure.

---

## The asymmetry we currently have

| layer | what gets proposed | grounded refutation gate | status |
|---|---|---|---|
| **findings** (sol_find output) | "this is a bug" | `halmos` symbolic refutation | ✓ wired (`score.py:halmos_signal`, gates via `MultiplicativeCritic`'s zero-kills-total) |
| **prompts** (sol_find.md, sol_intent.md) | "rewrite the prompt this way" | `_gate_rewrite` (shape check: placeholders, length, heading structure) | ✓ wired (`prompt_improve.py:114`) but only checks SHAPE not EMPIRICAL EFFECT |
| **rankers** (re-rank logic in `tools/scabench_rerank.py`) | "use signal X instead of eigenvector" | **NONE** | ✗ missing — I caught dedup + inversion manually via simulator |
| **dedup / filtering policies** | "skip duplicates at K" | **NONE** | ✗ missing — same |
| **signal-weighting** (the 0.6·eig + 0.3·katz + 0.1·bet in `_build_node_score_map`) | "change the weights" | **NONE** | ✗ missing |

`halmos` is the load-bearing primitive that makes the findings-side loop self-falsifying. There is no analog for the ranker-side, dedup-side, or signal-weighting-side. **That asymmetry is the gap between "components" and "just run."**

---

## The primitive: `ranking_fitness_gate`

```python
# tools/ranking_fitness_gate.py  (proposed)

from typing import Callable, Protocol

class RankingProposal(Protocol):
    """A proposed change to how findings are ordered. Anything callable that
    takes a list of findings + ctx and returns a re-ordered list."""
    def __call__(self, findings: list[dict], **ctx) -> list[dict]: ...


def ranking_fitness_gate(
    proposal: RankingProposal,
    *,
    label: str = "anon",
    reference: RankingProposal | None = None,   # added in build: see below
    reference_label: str = "baseline",
    scores_dir: str = "runs/scabench-scores/",
    baseline_dir: str = "corpus/scabench/baseline-results/",
    K: int = 10,
    kill_threshold: float = -0.005,
    kill_min_loser_majority: float = 0.66,
    only_projects: Iterable[str] | None = None,
) -> dict:
    """Sound-refutation gate for ranking-shaped proposals.

    Applies `proposal` to the baseline-finding list of every scored scabench
    project, simulates K-truncated macro F1 against the existing scorer_v2
    per-finding TP labels (the same trick `tools/h14_lift_simulator.py` uses),
    and returns a verdict.

    Returns:
        {
          "label": str,
          "macro_F1_baseline": float,
          "macro_F1_proposal": float,
          "delta": float,
          "per_project_delta": {pid: float, ...},
          "n_helped": int, "n_hurt": int, "n_flat": int,
          "kill": bool,           # True if proposal should NOT be greenlit
          "kill_reason": str,
        }

    Kill rule (composable, both must trigger for kill=True):
        1. overall macro F1 delta < kill_threshold AND
        2. of projects where |delta| > 0.005, the proposal hurts ≥ kill_min_loser_majority
           of them (i.e. it's not just one bad outlier dragging the macro number).

    Cost: $0. Reuses existing scorer_v2 per-finding judgments. Same call gives
    the loop a 24-project verdict in ~2 seconds.

    Sound-refutation property: a kill=True verdict means "this proposal made
    things worse on data we already have, before any new compute is spent."
    It's the analog of halmos returning COUNTEREXAMPLE for a findings claim —
    grounded, fast, cheap, hard-no.
    """
    ...
```

### `reference` parameter — added during build 2026-06-21

The build surfaced a real semantics issue not captured in the v1 spec. The
`proposal` is always evaluated against **some reference ordering**, not just
the GPT-5 confidence baseline. Concrete example from yesterday's session:
the question was "does dedupe-at-K improve on H14?" NOT "does H14+dedupe
improve on baseline?" — same data, different reference, different verdict
(H14+dedupe is +0.0066 vs baseline but -0.0210 vs H14, and the latter is
what got killed).

The gate now takes an optional `reference` callable:
- default `None` → reference is identity (= GPT-5 confidence ordering)
- pass any Proposal → compare proposal-vs-reference deltas
- `reference_label` for display

The 4-smoke sanity suite at the bottom of `tools/ranking_fitness_gate.py`
reproduces yesterday's `h14+dedupe` kill exactly: macro F1 -0.0210, 6/7
non-flat projects hurt (86% > 66% majority), kill=True.

### How the kill rule is "sound enough"

`halmos` is sound in the strict logical sense — a COUNTEREXAMPLE is a literal witness. `ranking_fitness_gate` is sound in a **scorer_v2-relative** sense: a kill verdict means the proposal would have produced lower macro F1 than baseline on the existing judgments. That's not metaphysical certainty about future runs (judgments could change with a new judge model), but it IS hard ground truth for the question "is this proposal worse on the data we have."

Both today's empirical kills hit this rule cleanly:
- **dedup**: macro F1 -0.0210, hurts 9/12 movers on H14 ordering → `kill=True`
- **inv_eig on losers**: -0.0344, hurts 6/6 losers (kill rule's stronger form) → `kill=True`

---

## Integration points

### (a) The synthesizer workflow's `Synthesize` phase
Every workflow that emits a `recommend X` line in its synthesis output should call `ranking_fitness_gate(X)` BEFORE returning the memo. The memo should include the gate verdict as a structured field, not just prose. Example shape:

```js
// in workflow script, after synthesis returns
for (const rec of memo.recommendations) {
  if (rec.kind === 'ranking_change') {
    rec.gate_verdict = await fitnessGate(rec.proposal)
    if (rec.gate_verdict.kill) rec.status = 'REFUTED_BY_GATE'
  }
}
return memo  // recommendations carry verdicts; ungated recommendations are flagged
```

The 14-agent workflow today wrote a 600-word memo recommending dedup and dataflow-distance without ever testing them. The gate fixes that pattern at the workflow level — no recommendation gets through without a verdict.

### (b) `prompt_improve.improve_if_weak`
Currently checks SHAPE (`_gate_rewrite`). Should also call `ranking_fitness_gate` when the rewrite proposes a logic change that affects ranking. Most prompt rewrites don't — they change wording, not ordering — but some do (e.g. sol_find.md adding/removing a severity-weighting clause). For those, the gate should hard-block negative rewrites.

This requires a lightweight static check to detect "does this prompt rewrite affect ranking-influencing output?" — a fuzzy property, but solvable in the dumb case (regex on "confidence", "severity", "rank", "order").

### (c) `score.MultiplicativeCritic`
Add the gate as an OPTIONAL hard-gate signal alongside halmos. When the system proposes changing the signal weights in `_build_node_score_map`, the critic runs `ranking_fitness_gate(new_weights_fn)` and zeros the total if killed. Same mechanic as halmos — sound refutation kills the score.

---

## How today's session would have played out, automatically

**14-agent diagnostic workflow** (`wf_5be2c20b-604`): same prompt, runs. Same per-project diagnostics returned. Same synthesis memo recommending dedup + dataflow-distance.

**WITH the gate primitive wired into the synthesis phase**, the workflow's last step automatically calls:
```python
gate(dedup_proposal)           # → {kill: True, delta: -0.0210, n_hurt: 9}
gate(invert_eig_proposal)      # → {kill: True, delta: -0.0344, n_hurt_losers: 6}
gate(setdefault_max_proposal)  # → {kill: False, delta: +0.0037, n_helped: 6}
```

The synthesizer's output memo now leads with:
> ❌ dedupe-at-K REFUTED by ranking_fitness_gate (delta -0.0210, hurts 9/12 movers)
> ❌ dataflow-distance/inv_eig proxy REFUTED by ranking_fitness_gate on H14-losers (delta -0.0344, 6/6 same sign)
> ✓ setdefault→max APPROVED (+0.0037, 6 helped 0 hurt). Ready to ship.

JH reads that, says "ship setdefault, what next?" — the loop never proposes a $30-50 Modal bet on a refuted hypothesis. ME-AS-FALSIFIER becomes LOOP-AS-FALSIFIER.

---

## What's still missing after this primitive lands

The gate only refutes **ranking-shaped** proposals. The loop will still produce wrong-bet recommendations for:

1. **Proposer-side changes** (e.g. "swap GPT-5 for Sonnet 4.6") — these need re-running the proposer against ground truth, which costs $5-10 Modal per test. No $0 simulator path because the new proposer's findings aren't in the existing scorer_v2 judgments by construction.
   - Mitigation: a *staged* version of the gate that runs the new proposer on the SMALLEST loser project (idle-finance: 5 expected bugs) before greenlighting the broader run. ~$1, ~5 min. Same sound-refutation property at smaller granularity.

2. **Judge-side changes** — same problem in reverse. Currently no plan.

3. **Architectural changes** that don't fit any existing measurement (e.g. "use a different graph representation"). These genuinely need new infrastructure and the gate can't help.

The gate is necessary but not sufficient for "just run." It closes the loop on the failure mode we hit today (ranker-side synthesizer over-fit). The proposer-side failure mode needs a separate primitive (staged-proposer-gate).

---

## Build plan (after JH approval of this spec)

1. **`tools/ranking_fitness_gate.py`** — extract the simulator's core into a callable that takes any `(findings, **ctx) → ordered_findings` function and returns the verdict dict. ~2 hours.
2. **Refactor `tools/h14_lift_simulator.py`** to use the new primitive. Existing behavior preserved, code dedups. ~30 min.
3. **Wire into workflow synthesis** — the `agent(synthPrompt, ...)` call in workflow scripts gets a post-hoc gate pass on its recommendations. ~1 hour.
4. **Add to `MultiplicativeCritic`** as optional signal — same mechanic as `halmos_signal`. ~30 min.
5. **Document in `CLAUDE.md`** — codify the new discipline: "when proposing a ranking change, call ranking_fitness_gate; respect kill=True." ~15 min.

Total: ~half day, $0 compute. Compounding payoff: every future ranker-side experiment gets free auto-refutation.

---

## Open questions for JH

- The kill threshold (-0.005 macro F1) is heuristic. Should we make it configurable per-proposal or tighten/loosen based on N-projects-touched? *Default in spec is heuristic; revisit after first 5 real uses.*
- Should the gate veto, or just warn-and-let-JH-decide? *Spec defaults to VETO (matches halmos). JH can override per-call. But if JH overrides 3+ times that's a signal the kill threshold is mis-tuned.*
- Should we extend the simulator to do bootstrap CI on the delta, so the gate has a statistical floor on "this is just noise"? *Yes, but as a v2 — v1 should ship with the dumb threshold and measure how often it's right.*

---

## Provenance

- Spec written: 2026-06-20 17:15 CDT
- Triggered by: today's session where I caught dedup + inversion manually via `tools/h14_lift_simulator.py` before either could become a $30-50 Modal bet
- Companion docs: [scabench/h14_lift_2026-06-20.md](../scabench/h14_lift_2026-06-20.md) (today's empirical kills), [scabench/scorecard.md](../scabench/scorecard.md) (2026-06-20 update section)
- Next concrete step: when JH approves, build per the plan above. Until then, this is the named primitive everyone (me, agents, future-JH reading this) can reference instead of re-deriving the pattern.
