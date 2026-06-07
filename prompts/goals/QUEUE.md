# Autonomous goal queue

Ranked queue for the autonomous loop. Format: one row per goal.
Picker reads top-to-bottom, picks first `pending` goal that fits
remaining weekly budget.

Status values: `pending` | `in-progress` | `done` | `disputed` | `blocked`
Cost estimates are PER-CYCLE upper bounds. Real spend tracked in
`tools/autonomous_spend.json`.

Edits to this file are honest curation. Picker re-reads every cycle.

| rank | goal | est_cost | status | notes |
|------|------|----------|--------|-------|
| 1 | LEAD_CONDITIONED_SPEC | $10 | blocked | architectural fix for v1 noise (ERC4337StaticSigDoS only) |
| 2 | CORPUS_GROWTH for S-3 | $0 | disputed | counter-increment-on-revert shape; sequence L-02 |
| 3 | CORPUS_GROWTH for S-4 | $0 | pending | cumulative-state-drift shape; sequence L-01 |
| 4 | CFG_DECODE extension (4 specs) | $5 | pending | author schemas for remaining specs |
| 5 | T7 HuggingFace push | $0 | pending | push reps + index + classifier to HF |
| 6 | T19 retrieval recall gap | $0 | pending | MissingAwait + missing-await query alignment |
| 7 | ROUTER_TRAIN refresh | $0 | pending | retrain with new ensemble reps |
| 8 | SLITHER baseline on remaining 3 corpora via cloud loop | $0 | pending | leverage the slither.yml workflow |

## Operating rules

- Picker SKIPS goals where `status != pending`
- Picker SKIPS goals whose `est_cost > remaining_budget`
- After execution, executor MUST update status: `in-progress` during run, then
  `done` if refuter PASSES or NULL-HONEST, or `disputed` if refuter splits
- Disputed goals STAY disputed (the picker skips them). JH reviews each one
  and either resets to `pending` or marks `blocked`.
- Autonomous edits to this file allowed ONLY to update status. New rows
  added by JH explicitly.
