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

## Self-extending rule (read before picking an item)

When you finish a pulse and notice fewer than 5 unchecked `[ ]` items
remain in this file, BEFORE you stop, append the templated items from
`## Refill templates` (at the bottom of this file) — pick the 3 most
relevant to current state and append them as new bounded items. This is
the queue's only autonomy: refill from the templated list, never invent
unbounded work.

## Items

- [x] **(P1) Foundry+halmos scaffold for puppy-raffle reentrancy (H-1).**
      Write `examples/puppy-raffle/foundry.toml` + `test/Properties.t.sol`
      with `check_refundIsBounded` using an Attacker contract whose `receive`
      re-enters `refund`. Expected halmos verdict: COUNTEREXAMPLE.
      Outcome: 2 new files committed; STATUS.md updated.
      commit: (this pulse)

- [x] **(P1) Foundry+halmos scaffold for puppy-raffle integer overflow (H-3).**
      Added `check_uint64CastDoesNotLoseFee` to puppy-raffle Properties.t.sol.
      Isolates the exact bug line (`uint64(fee)` cast in selectWinner) to
      give halmos a clean BitVec property; predicted COUNTEREXAMPLE on any
      fee ≥ 2**64. commit: (this pulse)

- [x] **(P2) Foundry+halmos scaffold for t-swap `x*y=k` invariant (H-5).**
      Write `examples/t-swap/foundry.toml` + `test/Invariants.t.sol`. After
      any sequence of swaps, `reserveX * reserveY >= k_before`. Expected:
      COUNTEREXAMPLE (H-5 says the extra-token-on-swapCount path breaks this).
      Used `vm.store` to seed `swap_count = 9` so the next swap immediately
      hits the bonus path; avoids 10-swap symbolic exploration. commit: (pulse)

- [x] **(P2) Audit `reps.jsonl` for schema drift.** Read all 20 rows,
      confirm each has `contract`, `proposer`, `score`, `verifier`,
      `prior`, `embed_coords`. Write `tools/validate_reps.py` (tiny).
      Outcome: validator script + a CI hook in `.github/workflows/`.
      Result: OK 20/20 rows pass; sanity.yml runs on every push/PR.
      commit: (pulse)

- [x] **(P3) MCP tool definitions for plumbline.** Wrap `sol_match.match`,
      `halmos_rep.run_one`, `scoreboard.main` as MCP tools (one Python file
      with `@mcp.tool` decorators). Outcome: `mcp_server.py`, importable
      from any Claude session. (Per JH user rule: "If you CAN mcp it,
      mcp it.")
      Result: mcp_server.py + .mcp.json — 5 tools exposed
      (plumbline_match, plumbline_scoreboard, plumbline_validate,
      plumbline_halmos_rep, plumbline_status). sol_intent deliberately
      NOT exposed (LLM-spend gate). commit: (pulse)

- [x] **(P3) Add `.github/workflows/loop.yml`** that runs the rep loop on
      every push to main: install deps → run all `examples/*` with
      `model_rep.py` skipping if no API key → commit any new reps.jsonl
      rows → push back. Self-extending dataset.
      Two jobs: `scoreboard` (deterministic, always runs) +
      `reps` (gated on PACT_LLM_API_KEY secret; SKIPS if absent, costs
      ~$1/push if present). Auto-commits new rows. commit: (pulse)

- [x] **(P4) `tools/fitness_card.py`:** generate a single PNG card from
      `reps.jsonl` showing recall/precision per corpus over time. Just
      matplotlib, no fancy embedding work. Output: `docs/fitness.png`.
      Lazy matplotlib import (skips gracefully if missing — CI safe).
      Two stacked subplots (recall + precision) vs rep order in file, one
      colored line per corpus. Syntax-checked. PNG renders when run.
      commit: (pulse)

- [ ] **(P4) Curate one more corpus.** Cyfrin's `7-bridges-audit` or
      `8-vault-guardians-audit` — same procedure as puppy-raffle/t-swap/
      thunder-loan. Each adds ~15 real findings to the corpus.

- [ ] **(P5) Cleanup pass:** verify CLAUDE.md / STATUS.md / README.md are
      mutually consistent. Trim stale notes.

### Refilled 2026-06-05 (template-derived, P4/P5)

- [ ] **(P4) Halmos scaffold for thunder-loan H-1 storage collision.**
      Write `examples/thunder-loan/foundry.toml` + `test/Properties.t.sol`
      with `check_storageSlotsConsistent` comparing the slot layout of
      `ThunderLoan` vs `ThunderLoanUpgraded`. Expected: COUNTEREXAMPLE
      (s_flashLoanFee at different slot in upgrade). Update setup.sh
      to forge install OZ-upgradeable.

- [ ] **(P4) Curate examples/boss-bridge from Cyfrin/7-boss-bridge-audit.**
      Same procedure as puppy-raffle/t-swap/thunder-loan: gh api the
      audit-data report, write `.ANSWERS.md` aligned to sol_match's
      section tokenizer, copy `src/`, verify section count.

- [ ] **(P5) Per-corpus `README-bugs.md` for puppy-raffle.** Cross-reference
      each finding from `.ANSWERS.md` to the specific line range in
      `PuppyRaffle.sol`. Keeps the corpus auditable without re-reading the
      original Cyfrin report.

## Hard stops

- If item count drops to 0 AND refill templates exhausted: append a single
  line "queue empty 2026-MM-DD" to STATUS.md, push, end the cron.
- If a single pulse takes >3 commits: stop. Drift detected.
- If JH messages: cron yields immediately on next idle window.

## Refill templates (used by self-extending rule)

Pick 3 most relevant when items run low. Each is bounded, deterministic,
verifiable. Cyfrin audit-data layout is known (`audit-data/<date>-<name>.md`
on the `audit-data` branch).

### Curation templates
- Curate `examples/<name>` from Cyfrin/N-<name>-audit. Copy `src/`, extract
  finding sections from canonical audit-data report via `gh api`, write
  `.ANSWERS.md` matching sol_match's section tokenizer. Verify section
  count vs finding count.
- Candidates not yet curated: bridges audit, vault-guardians audit,
  boss-bridge audit, password-store audit. Use `gh api` to find each repo's
  audit-data branch first.

### Halmos scaffold templates
- For each curated `examples/<name>` that has a Foundry-style src layout:
  write `foundry.toml` (solc version from `pragma solidity` of source) +
  `test/Properties.t.sol` with at least one `check_*` symbolic invariant
  targeting a HIGH finding from `.ANSWERS.md`. Predict halmos verdict in a
  comment. Update `.devcontainer/setup.sh` so a Codespace boot picks up
  the new scaffold.

### Documentation templates
- For each `examples/<name>`, write a short `README-bugs.md` cross-referencing
  the planted/curated bugs to specific lines in the source. Keeps the
  corpus readable without re-running the audit.
- Update `CLAUDE.md` with any new Layer 1 contract changes (only after a
  REAL rep surfaces a bug — never speculative).
- Trim or refactor `STATUS.md` to keep it under 100 lines and accurate.

### Tooling templates
- Add a tiny CLI flag to `scoreboard.py`: `--corpus <name>` filters to one
  group. Useful when comparing pulses.
- Add `tools/dedup_reps.py` that detects and reports duplicate rep_ids
  (should never happen, but if it does we want to know).
- Add `tools/replay.py` that re-prints the score for a given `rep_id` from
  `reps.jsonl` — useful for sanity-checking historical reps.
- Add a single GH Actions workflow `.github/workflows/sanity.yml` that
  runs `python -c 'import json; [json.loads(l) for l in open("reps.jsonl")]'`
  on every push (validates the dataset stays parseable).

### MCP templates
- Wrap one plumbline function as an MCP tool at a time (sol_match.match
  first, then scoreboard.main, then halmos_rep.run_one).
