# TODO — Autonomous Pulse Queue

This file drives the autonomous cron. Each pulse: pick the topmost
`[ ]` item, execute, change to `[x]` with a `commit:` line, push.

## Rules of engagement

1. **Bounded only.** Each item lists its bounded outcome. If you can't
   verify the outcome from where you sit, mark it `[skip: <reason>]` and
   move down.
2. **No money.** Do NOT call `sol_intent` / any LLM-proposer. The cron pulse
   is for deterministic work only — curation, scaffolding, refactoring.
3. **No re-tuning `sol_match.py`.** Six rounds in one session is the cap.
4. **No Layer 2 (hyperbolic embedding).** Locked behind 50 reps + δ measure.
5. **Every pulse pushes.** If `git push` fails, mark item `[blocked]` and stop.
6. **No theater.** If the work isn't verifiable when JH returns, skip it.
7. **STATUS.md is the source of truth for "what JH sees first."** Update it
   when an item lands.

## Items

- [ ] **(P1) Foundry+halmos scaffold for puppy-raffle reentrancy (H-1).**
      Write `examples/puppy-raffle/foundry.toml` + `test/Properties.t.sol`
      with `check_refundIsBounded` using an Attacker contract whose `receive`
      re-enters `refund`. Expected halmos verdict: COUNTEREXAMPLE.
      Outcome: 2 new files committed; STATUS.md updated.

- [ ] **(P1) Foundry+halmos scaffold for puppy-raffle integer overflow (H-3).**
      Write a `check_totalFeesNoOverflow` test that asserts no `uint64`
      truncation as cumulative fees grow. Expected: COUNTEREXAMPLE.

- [ ] **(P2) Foundry+halmos scaffold for t-swap `x*y=k` invariant (H-5).**
      Write `examples/t-swap/foundry.toml` + `test/Invariants.t.sol`. After
      any sequence of swaps, `reserveX * reserveY >= k_before`. Expected:
      COUNTEREXAMPLE (H-5 says the extra-token-on-swapCount path breaks this).

- [ ] **(P2) Audit `reps.jsonl` for schema drift.** Read all 20 rows,
      confirm each has `contract`, `proposer`, `score`, `verifier`,
      `prior`, `embed_coords`. Write `tools/validate_reps.py` (tiny).
      Outcome: validator script + a CI hook in `.github/workflows/`.

- [ ] **(P3) MCP tool definitions for plumbline.** Wrap `sol_match.match`,
      `halmos_rep.run_one`, `scoreboard.main` as MCP tools (one Python file
      with `@mcp.tool` decorators). Outcome: `mcp_server.py`, importable
      from any Claude session. (Per JH user rule: "If you CAN mcp it,
      mcp it.")

- [ ] **(P3) Add `.github/workflows/loop.yml`** that runs the rep loop on
      every push to main: install deps → run all `examples/*` with
      `model_rep.py` skipping if no API key → commit any new reps.jsonl
      rows → push back. Self-extending dataset.

- [ ] **(P4) `tools/fitness_card.py`:** generate a single PNG card from
      `reps.jsonl` showing recall/precision per corpus over time. Just
      matplotlib, no fancy embedding work. Output: `docs/fitness.png`.

- [ ] **(P4) Curate one more corpus.** Cyfrin's `7-bridges-audit` or
      `8-vault-guardians-audit` — same procedure as puppy-raffle/t-swap/
      thunder-loan. Each adds ~15 real findings to the corpus.

- [ ] **(P5) Cleanup pass:** verify CLAUDE.md / STATUS.md / README.md are
      mutually consistent. Trim stale notes.

## Hard stops

- If item count drops to 0: append a single line "queue empty 2026-MM-DD"
  to STATUS.md, push, end the cron.
- If a single pulse takes >3 commits: stop. Drift detected.
- If JH messages: cron yields immediately on next idle window.
