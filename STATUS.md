# Status — 2026-06-05, end of unsupervised session

Welcome back. Here is exactly what is real, what is hypothesized, and the
two commands to validate the hypothesis when you open the Codespace.

## What is real (verified)

- 20 reps in `reps.jsonl` from this morning's session — recall=1.0 saturated
  on three synthetic twins, precision 0.25–0.50, wrong-corpus probe drops to
  0.09. All committed to GH; survives Codespace reboots.
- 5 Layer 1 tokenizer/matcher bugs surfaced AND fixed via reps (see
  `CLAUDE.md` — each tied to a real `rep_id`).
- `puppy-raffle/.ANSWERS.md` — 16 findings (4H/4M/8I), curated from the
  canonical Cyfrin audit-data branch report. Section-tokenized, ready for
  `sol_match` scoring.
- `synthetic-dreusd/foundry.toml` + `test/Properties.t.sol` — Foundry +
  halmos scaffold with two symbolic invariants targeting the planted
  decimals bug. Compiles in pattern; not yet run.
- `puppy-raffle/foundry.toml` + `test/Properties.t.sol` — Attacker contract
  + `check_refundDoesNotPayTwice` targeting H-1 reentrancy (CEI violation
  in `refund`); plus `check_uint64CastDoesNotLoseFee` targeting H-3
  (`uint64(fee)` truncation in `selectWinner`). Both predicted halmos
  verdicts: COUNTEREXAMPLE. Setup.sh updated to forge install OpenZeppelin
  v3.4.2 + Brechtpd/base64.
- `boss-bridge/.ANSWERS.md` + sources — 4th real corpus, 13 findings (8H + 1M +
  3L + 1I) curated from Cyfrin/7-boss-bridge-audit. Total curated real findings:
  16 + 11 + 14 + 13 = 54 across 4 protocols.
- `t-swap/foundry.toml` + `test/Invariants.t.sol` — `check_swapPreservesXYK`
  targeting H-5 (the 1e18 bonus token transfer every SWAP_COUNT_MAX=10
  swaps breaks the constant-product invariant). `vm.store` seeds
  `swap_count = 9` so the next swap immediately hits the bonus path.
  Predicted halmos verdict: COUNTEREXAMPLE. Setup.sh updated to forge
  install OpenZeppelin v4.x for solc 0.8.20.

## What is hypothesized (unverified)

Halmos has not run from my session. The scaffold is the hypothesis:

- `check_redeemReturnsDeposit(uint256 deposit)` — predicted verdict:
  **COUNTEREXAMPLE** (redeem misses `/1e12`; user receives `deposit * 1e12`
  USDC instead of `deposit`).
- `check_supplyAtMostBacking(uint256 deposit)` — predicted verdict:
  **COUNTEREXAMPLE** (same root cause; outstanding obligation exceeds USDC
  reserves after the first mint).

If halmos returns PROVED on either, my reading of the bug is wrong somewhere
and the scaffold needs fixing — that is itself useful signal.

If halmos returns TIMEOUT, bump `--solver-timeout-assertion` and/or tighten
the `vm.assume` bounds.

## Two commands to validate when you open the Codespace

```bash
# 1. Real-corpus rep (sol_intent on puppy-raffle vs the 16 curated findings)
./.venv/bin/python model_rep.py examples/puppy-raffle
./.venv/bin/python scoreboard.py   # see the new row in the aggregate

# 2. Halmos verdict on the synthetic-dreusd Properties (Foundry + halmos)
cd examples/synthetic-dreusd
forge install --no-commit foundry-rs/forge-std transmissions11/solmate   # if setup.sh skipped
../../.venv/bin/halmos --function check --solver-timeout-assertion 120000
cd -
./.venv/bin/python halmos_rep.py examples/synthetic-dreusd   # logs the verdict to reps.jsonl
```

The first command tells you whether `sol_intent`'s recall holds OFF the
saturated synthetic distribution. (Honest prior: I expect a real drop. The
findings list is more diverse than the planted bugs and uses different
vocabulary.)

The second command tells you whether halmos discharges the symbolic
invariants. (Honest prior: COUNTEREXAMPLE on both, with concrete EVM traces.)

## What I did NOT do (and why)

- Did not run halmos myself — local `.venv` was freed for disk; the
  Codespace exec/ssh path is blocked by the sshd-vs-Foundry tradeoff per
  memory. Scaffold was the most I could honestly deliver.
- Did not re-tune `sol_match.py` further. Six rounds is plenty without you
  in the loop; more rounds alone = curve-fitting risk.
- Did not start Layer 2 (hyperbolic embedding). Still parked behind 50-rep
  gate + δ-measurement.
- Did not run more `sol_intent` reps. Each one is real money/latency; I
  preferred to land the puppy-raffle corpus and the halmos scaffold so YOUR
  next session is more informative than another stochastic sweep would be.

## MCP server

`mcp_server.py` exposes 5 plumbline tools to any MCP host (Claude Desktop /
Code / Codespace): `plumbline_match`, `plumbline_scoreboard`,
`plumbline_validate`, `plumbline_halmos_rep`, `plumbline_status`. `.mcp.json`
ships the host config. `sol_intent` (LLM-spend) is deliberately NOT exposed.

Wire it up: `pip install fastmcp` then point your host at `.mcp.json`.

## Codespace info

- Repo: `qizwiz/plumbline` @ `e8190c0` (main)
- Codespace: `organic-dollop-9qjvgq9pp39xpr` (32GB / 4 vCPU)
- Open via: `gh codespace code -c organic-dollop-9qjvgq9pp39xpr` or the GH UI.
- Local: `~/src/plumbline` is 1.4M (source only; `.venv` was freed).
