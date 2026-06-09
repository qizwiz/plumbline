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
| -1 | CONTEST_DAY_HARDENING | $0 | in-progress | criteria #1-7 done. Criterion #8 cascade-layer verified: DRE source (kunalsz/dre) committed to examples/dreusd-real/; 12 cascade leads → 3 survivors after filters: fillWithdrawal caught (onlyRole), dreShareOFT.initialize caught (ATOMIC_INIT+deployShareOFT.s.sol atomic proxy), requestExpressWithdrawal survives (public, batch-DoS path). adversarial_verify.py: 2 fixes — ATOMIC_INIT triggers on func_name==initialize; _PROXY_INIT_RE handles abi.encodeWithSelector+ERC1967Proxy{salt:}. Full baseline (≤30 from ~182) pending — run locally with: python tools/contest_day.py examples/dreusd-real/ --slug 2026-06-08-dre-app --sponsor "DRE App" --target sherlock --out-dir reports/ |
| 0 | SHAPE_GRAPH_EVOLVE | $0 | done | All 8 criteria met. --runs 10 (90 TLC invocations): 3 novel mutations generated (Create2NonIdempotent_mut_4, CrossWalletSigReplay_mut_8, ReentrancyDrain_mut_7). All inject mutations anti-sim blocked by OracleStaleness (cos 0.87-0.88); non-inject mutations cover 0 unmatched findings. Ranking JSON updated. Next lever: semantic operators targeting the 146-finding gap cluster (oracle/timing/economic bugs). |
| 1 | NOTIONAL_RECALL | $15 | done | 67.6% strict mechanical, 75.6% honest combined cold recall on Sherlock-judged Notional. Gap to ceiling = 18pp. See CALIBRATION_NOTIONAL_RECALL.md. |
| 2 | STRUCTURAL_CASCADE | $0 | done | v3: 6/6 H/M strict (100%), 13 final from 145 fns. 294 SLOC. All 8 criteria met. |
| 3 | LEAD_CONDITIONED_SPEC | $10 | blocked | architectural fix for v1 noise (ERC4337StaticSigDoS only) |
| 4 | CORPUS_GROWTH for S-3 | $0 | disputed | counter-increment-on-revert shape; sequence L-02 |
| 5 | CORPUS_GROWTH for S-4 | $0 | disputed | cumulative-state-drift shape; sequence L-01 |
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
