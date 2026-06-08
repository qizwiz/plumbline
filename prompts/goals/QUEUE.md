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
| -4 | DRE_DEEPER_MINE_2026-06-08 | $5 | done | Contest 1259 closed 2026-06-17. Final filing (2026-06-16): 5 issues open (H1 first-depositor inflation, M1 paused-distributor pricing, W1 pre-fee slippage, C1 sequencer staleness, Co3 dustless redeem) + 3 closed-with-rationale per Phase D adversarial review. See project_sherlock1259_postmortem memory. |
| -3 | VECTOR_DB_AS_DISCOVERY_ENGINE | $0 | done | 2026-06-08 DRE contest: corpus clustering (1240 H/M findings → 50 clusters via k-means on bge-small embeddings) → NN-rank 157 DRE concrete functions → manually verify top hypotheses → produced 1 HIGH-severity finding (first-depositor inflation via vested-rewards channel) filed as Sherlock issue #1. 3 PoCs verified, production-path passes against KEEPER → mintRewards → addRewards flow. Validation CI repo at qizwiz/dreusd-poc-validation. The workflow that produced this: corpus_clusters_k50.json → DRE NN top-50 → adversarial verification of top H matches. REPRODUCE on next contest. |
| -2 | BATCH_REVERT_ROLLBACK_SHAPE | $0 | pending | Brutal structural cascade on DRE (2026-06-08) flagged `unbounded_for` AST signature on fillWithdrawal AND fillExpressWithdrawals; 0/10 TLA+ shapes matched the underlying batch-revert-rolls-back-prior-iterations pattern. Library has no such shape. Bank via SHAPE_GRAPH_EVOLVE: action_subdivide on a sig-replay-style loop spec → introduce abort-on-fail variable → check `BatchAtomicity` invariant. Counterexample = the trace already exhibited in dreUSDManager L543-560. |
| -1 | CONTEST_DAY_HARDENING | $0 | done | All 8 criteria met. FIX5: Sherlock render-path bug fixed — non-HIGH leads (HIGH-static/MEDIUM-static/NORMAL) were silently dropped to QA and invisible in Sherlock H/M template; now route as MEDIUM → Medium bucket. render_report.py+contest_day.py updated. Simulation verified: 1 High + 3 Medium + 1 QA-dropped for 5 test leads. Needs real sol_intent run for live confirmation (no API key in cloud env). |
| 0 | SHAPE_GRAPH_EVOLVE | $0 | done | All 8 criteria met. --runs 10 (90 TLC invocations): 3 novel mutations generated (Create2NonIdempotent_mut_4, CrossWalletSigReplay_mut_8, ReentrancyDrain_mut_7). All inject mutations anti-sim blocked by OracleStaleness (cos 0.87-0.88); non-inject mutations cover 0 unmatched findings. Ranking JSON updated. Next lever: semantic operators targeting the 146-finding gap cluster (oracle/timing/economic bugs). |
| 1 | NOTIONAL_RECALL | $15 | done | 67.6% strict mechanical, 75.6% honest combined cold recall on Sherlock-judged Notional. Gap to ceiling = 18pp. See CALIBRATION_NOTIONAL_RECALL.md. |
| 2 | STRUCTURAL_CASCADE | $0 | done | v3: 6/6 H/M strict (100%), 13 final from 145 fns. 294 SLOC. All 8 criteria met. |
| 3 | LEAD_CONDITIONED_SPEC | $10 | blocked | architectural fix for v1 noise (ERC4337StaticSigDoS only) |
| 4 | CORPUS_GROWTH for S-3 | $0 | done | CounterIncrementOnRevert.tla — TLC: BudgetReflectsActualUse VIOLATED in 2 states. Grammar PASS. Retrieval top-1 cos=0.829. Corpus size 20. Cites sequence L-02. |
| 5 | CORPUS_GROWTH for S-4 | $0 | done | CumulativeStateDrift.tla — TLC: CumulativeLimitHolds VIOLATED in 3 states. Grammar PASS. Retrieval top-1 cos=0.788. Corpus size 21. Cites sequence L-01. |
| 6 | CFG_DECODE extension (4 specs) | $5 | done | author schemas for remaining specs |
| 7 | T7 HuggingFace push | $0 | done | push reps + index + classifier to HF |
| 8 | T19 retrieval recall gap | $0 | done | MissingAwait + missing-await query alignment |
| 9 | ROUTER_TRAIN refresh | $0 | done | retrain with new ensemble reps |
| 10 | SLITHER baseline on remaining 3 corpora via cloud loop | $0 | disputed | leverage the slither.yml workflow |

## Operating rules

- Picker SKIPS goals where `status != pending`
- Picker SKIPS goals whose `est_cost > remaining_budget`
- After execution, executor MUST update status: `in-progress` during run, then
  `done` if refuter PASSES or NULL-HONEST, or `disputed` if refuter splits
- Disputed goals STAY disputed (the picker skips them). JH reviews each one
  and either resets to `pending` or marks `blocked`.
- Autonomous edits to this file allowed ONLY to update status. New rows
  added by JH explicitly.
