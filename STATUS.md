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

## Codespace info

- Repo: `qizwiz/plumbline` @ `e8190c0` (main)
- Codespace: `organic-dollop-9qjvgq9pp39xpr` (32GB / 4 vCPU)
- Open via: `gh codespace code -c organic-dollop-9qjvgq9pp39xpr` or the GH UI.
- Local: `~/src/plumbline` is 1.4M (source only; `.venv` was freed).
