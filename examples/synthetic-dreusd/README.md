# dreUSD

A USD-pegged stablecoin and yield vault. **Real yield, paid daily.**

dreUSD is a stablecoin backed one-to-one by USDC and short-duration real-estate credit. dreUSDs is the
staking vault: stake dreUSD and earn the protocol's daily yield.

## Design

- **dreUSD** (`dreUSD.sol`) — the stablecoin. Mint by depositing USDC at \$1 → 1 dreUSD; redeem 1 dreUSD
  → \$1 of USDC. Every dreUSD in circulation is backed one-to-one by USDC the protocol holds.
- **dreUSDs** (`dreUSDs.sol`) — the yield vault (ERC-4626). Stake dreUSD to receive dreUSDs shares; the
  keeper pays the day's yield into the vault and it accrues to stakers.

## Guarantees

1. **Full backing.** dreUSD total supply is always covered by USDC backing; unbacked dreUSD cannot exist.
2. **1:1 peg, both ways.** A mint→redeem round-trip returns exactly what you put in — no value created.
3. **Fair, time-weighted yield.** Stakers earn yield in proportion to their stake *and the time they
   remain staked*. Capital is rewarded for commitment; a depositor cannot capture yield they did not
   earn by arriving just before a distribution and leaving just after.

> *(Synthetic protocol — a stand-in for Sherlock #1259, used to rehearse the audit. The implementation
> is written to look like a plausible funded-team build. Whether it actually upholds the three
> guarantees above is the exercise.)*
