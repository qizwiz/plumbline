# dreStaking (synthetic) — stake dreUSD, earn streamed rewards

`dreStaking` lets holders stake dreUSD and earn rewards that the protocol funds and streams linearly over
a fixed period (Synthetix-style `rewardPerToken` accumulator). It is operated by a single trusted
`REWARDS_ADMIN` (the protocol multisig).

## Guarantees the protocol promises

- **G1 — conservation of rewards.** Every dreUSD funded into the reward reserve is eventually distributed
  to stakers in proportion to stake × time; funding a new reward period MUST carry over any rewards from
  the current period that have not yet streamed (no funded reward is ever silently dropped).
- **G2 — admin-only economics.** Only `REWARDS_ADMIN` may set the reward rate, fund the reserve, or move
  reserve funds. A non-admin can stake, unstake, and claim — nothing else.
- **G3 — rounding favors the protocol.** Wherever a reward or share amount is rounded, it rounds DOWN
  (against the user). The protocol never pays out a wei it did not owe.
- **G4 — clean round-trip.** `stake(x)` immediately followed by `unstake(x)` returns exactly `x` dreUSD and
  accrues zero reward for the zero elapsed time.
