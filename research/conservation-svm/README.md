# Conservation engine — sound, self-discovering invariant checks for Solidity

`graph → auto-propose a conservation invariant → halmos discharges it`
(counterexample = bug, proof = the law holds). **Ethos: never false.** Precision is pinned at 1.0 *by
soundness* — a finding only exists if symbolic execution produced a witness that appears verbatim in halmos
stdout. Recall is the dial we climb; we never trade soundness for it.

The interesting part isn't "an LLM writes a test." It's that **no human writes the invariant for a given
contract** — the engine induces a reusable conservation *rule* from one seed bug and transfers it, by role,
to a contract it has never seen; a sound checker (halmos) is the only thing allowed to say "confirmed."

## What's proven (every result carries a FAIL-buggy / PASS-clean discrimination control)

- **Idiom #1 — round-trip conservation** (`conserve.py`): caught a dreUSD 18-vs-6-decimal redeem drain.
- **Idiom #2 — aggregate↔collection delta** (`conserve_agg.py`): caught a burn-forgets-`totalSupply` desync.
- **L2 idiom *discovery*** (`discover.py`): an LLM induces the invariant *class* from one seed and transfers
  it to a different-surface held-out contract; halmos validates. No human writes the per-contract idiom.
- **Real-external transfer** (2026-06-27, adversarially re-verified): induced a conservation law from a seed
  token bug and transferred it to held-out **StakingRewards** (Synthetix/Idle, OZ libs) — mapping
  `totalSupply`→aggregate, `balanceOf`→holding on a contract it had never seen. Result: **clean `[PASS]`
  (non-vacuous)** + **`Counterexample` on a one-line mutant** (`_totalSupply -= amount` deleted from
  `withdraw()`). Artifact: `discharge-idle/test/Discovered.t.sol`.
- **Decline control**: handed the same conservation idiom and an *access-control* contract (`AdminVault`),
  the engine **declined** — recognized no conservation pair exists rather than fabricating a law.
- **Determinism**: 4/4 independent inductions (3 re-samples + a different seed) produced the same law and the
  same correct role-mapping, zero fabrications (`discovery/resample/`).

## The soundness firewall actually fired

On the real-external run, `discover.py`'s *raw* emitted harness was **vacuous** — it mocked the staking token
but the contract calls `safeTransferFrom` unconditionally, so every symbolic path reverted and halmos printed
`all paths reverted / too restrictive`. A naive pipeline logs that as a green PASS. This one **refused to
count it**, named why, and repaired only the harness plumbing (a MockERC20) — the induced rule and assertions
preserved verbatim. The adversarial verifier then re-ran halmos itself and proved non-vacuity with a
deliberately-false-assert probe. That self-catching is the point.

## Honest limits (these travel with every claim)

- **n=1 on the target axis.** Proven on *a* real held-out contract, not many. Next: a second real target.
- **The bug *class* is human-seeded.** `discover.py` hardcodes the class hint ("aggregate desync"); the model
  does the role-*mapping*, not class *discovery*. Fully-autonomous next-step: derive the class from the
  seed's own halmos counterexample.
- **Emit-path harness can be vacuous** (the issue caught above) — it needs auto-mocking of unconditional
  external calls to be non-vacuous by construction. Until then a `[PASS]` only counts if `paths>1` and the
  symbolic inputs actually constrain state.
- **Mutation, not a wild bug.** The catch is a deliberate one-line analog of the seed bug — it demonstrates
  *transfer + discrimination*, not field bug-finding (that's the "first un-mutated Etherscan catch" milestone).
- **Backend reach.** halmos discharges single-contract laws (~the accounting/access/arith slice). The money
  family — price manipulation — lives in forked cross-protocol AMM state and needs a fork-state verifier; out
  of scope here, by design, not by omission.

## Reproduce

```bash
# real-external transfer: induce from a seed bug, transfer to held-out StakingRewards, validate
python3 discover.py fixtures/MiniTokenBug.sol discharge-idle/src/StakingRewards.sol StakingRewards
cd discharge-idle && forge build
uvx halmos --function check_invariant --contract DiscoveredTest        # clean -> PASS (non-vacuous)
uvx halmos --function check_invariant --contract DiscoveredTestMutant   # mutant -> Counterexample
```

Full record: `FINDINGS.md`. Ranked next moves: `NEXT.md`.
