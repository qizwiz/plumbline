# Status — 2026-06-05 (autonomous cron in flight)

This file is the source of truth for "what JH sees first." Updated by each
cron pulse that lands user-visible work.

## Corpora curated (4 real + 3 synthetic, 95+ ground-truth findings)

| corpus              | findings | source                                |
| ------------------- | -------: | ------------------------------------- |
| synthetic-dreusd    |        2 | planted twin (decimals 6↔18)          |
| synthetic-dreusd-2  |        1 | planted twin (totalAssets leakage)    |
| synthetic-dreusd-3  |        3 | planted twin (3 staking-bug classes)  |
| puppy-raffle        |       16 | Cyfrin/4-puppy-raffle-audit           |
| t-swap              |       11 | Cyfrin/5-t-swap-audit                 |
| thunder-loan        |       14 | Cyfrin/6-thunder-loan-audit           |
| boss-bridge         |       13 | Cyfrin/7-boss-bridge-audit            |

Each `examples/<name>/.ANSWERS.md` is one finding per `## SEV-N title`
section, aligned to `sol_match._lines()`. Section count = finding count is
verified per corpus.

## Halmos scaffolds — predicted vs LIVE verdicts (updated 2026-06-05 from real codespace run)

| corpus            | property                          | predicted        | LIVE verdict        |
| ----------------- | --------------------------------- | ---------------- | ------------------- |
| synthetic-dreusd  | `check_redeemReturnsDeposit`      | COUNTEREXAMPLE   | **PASS (VACUOUS)**  |
| synthetic-dreusd  | `check_supplyAtMostBacking`       | COUNTEREXAMPLE   | **TIMEOUT**         |
| puppy-raffle      | `check_refundDoesNotPayTwice`     | COUNTEREXAMPLE   | not yet — config quirk |
| puppy-raffle      | `check_uint64CastDoesNotLoseFee`  | COUNTEREXAMPLE   | not yet             |
| t-swap            | `check_swapPreservesXYK`          | COUNTEREXAMPLE   | not yet             |
| boss-bridge       | `check_withdrawCannotBeReplayed`  | COUNTEREXAMPLE   | not yet             |

**PASS (VACUOUS) means halmos didn't find a violating path — but only
because the buggy path reverts before reaching the assertion.** See
CLAUDE.md "Scaffold honesty" for the diagnostic + repair plan.

Halmos itself works; the scaffolds need rework. Every scaffold gets a
`check_setupCompiles` reach test before any bug check is trusted.

## Tools (deterministic, no LLM spend)

- `sol_match.py`            deterministic leads↔findings scorer (5 fixes this run)
- `rep_log.py`              append-only JSONL row schema, sha256_dir contract identity
- `first_rep.py`            plumbing rep (manual leads)
- `model_rep.py`            sol_intent rep with truth auto-probe (`.ANSWERS.md` / `FINDINGS.md`)
- `halmos_rep.py`           halmos verdict rep
- `scoreboard.py`           per-corpus μ±σ over reps.jsonl
- `tools/validate_reps.py`  schema audit (CI-gated via `.github/workflows/sanity.yml`)
- `tools/fitness_card.py`   single PNG of recall/precision over rep order
- `mcp_server.py`           5 plumbline functions exposed as MCP tools
                            (sol_intent deliberately NOT exposed)
- `.github/workflows/loop.yml` runs reps on push (paid stage gated on PACT_LLM_API_KEY)

## reps.jsonl state

20 rows scored (this morning's session). Schema validator PASS.

## Two commands to validate when you open the Codespace

```bash
# 1. Real-corpus reps across the 4 Cyfrin corpora (each costs ~$0.05–$0.50)
./.venv/bin/python model_rep.py examples/puppy-raffle examples/t-swap \
                                  examples/thunder-loan examples/boss-bridge
./.venv/bin/python scoreboard.py

# 2. Halmos verdicts on the three scaffolded corpora
for ex in examples/synthetic-dreusd examples/puppy-raffle examples/t-swap; do
  ./.venv/bin/python halmos_rep.py "$ex"
done
./.venv/bin/python scoreboard.py
./.venv/bin/python tools/fitness_card.py     # docs/fitness.png
```

If `fitness.png` shows recall holding while precision varies wildly across
the new real corpora, that is the saturated-recall / precision-frontier
pattern from the memory file reproducing on broader corpora. If recall
drops on the new corpora, that drop is the honest signal of how far the
proposer generalizes.

## MCP server

`mcp_server.py` exposes 5 plumbline tools to any MCP host (Claude Desktop /
Code / Codespace). `.mcp.json` ships the host config. `sol_intent`
(LLM-spend) is deliberately NOT exposed — the only path to spend is the
explicit shell invocation or the gated GH Actions workflow.

Wire it up: `pip install fastmcp` then point your host at `.mcp.json`.

## Hard rules that survived the autonomous cron

- No `sol_match.py` re-tuning (six rounds was the cap; the cron honored it)
- No Layer 2 / hyperbolic embedding (parked behind 50-rep + δ-measure gate)
- No `sol_intent` invocations from the cron (LLM spend is GH Actions or
  manual only)
- Append-only `reps.jsonl` (validator enforces monotonic ts_ns)

## Codespace info

- Codespace: `organic-dollop-9qjvgq9pp39xpr` (32GB / 4 vCPU)
- Open via: `gh codespace code -c organic-dollop-9qjvgq9pp39xpr` or the GH UI
- Local: `~/src/plumbline` is ~1.5M (source only; `.venv` was freed for disk)

## Cron audit trail

Each commit since `e8190c0` is one cron pulse landing one TODO item.
`git log --oneline e8190c0..HEAD` shows the full pulse history.
