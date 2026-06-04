# dreUSD (synthetic twin) — intent / promised invariants

> A SYNTHETIC stand-in for the DRE App / dreUSD protocol (Sherlock #1259), built from the public
> scope + "REAL YIELD. PAID DAILY." model, with canonical bugs **planted on purpose** so we can rehearse
> the audit and validate plumbline + the intent piece against ground truth *before* the real code drops.

dreUSD is a USD-pegged stablecoin. dreUSDs is the yield-bearing staking vault. Backing is private
real-estate credit; yield is paid daily to stakers.

## What the protocol PROMISES (the intent — verify the code against THIS)

1. **1:1 backing.** Every dreUSD in existence is backed by USDC held by the protocol. `dreUSD.totalSupply()`
   must never exceed the USDC backing. Minting unbacked dreUSD is impossible.
2. **1:1 mint/redeem.** Deposit $X of USDC → receive X dreUSD. Redeem X dreUSD → receive $X of USDC.
   No value is created or destroyed in the round-trip.
3. **Fair yield.** Daily yield in dreUSDs is earned **in proportion to time-weighted stake**. A depositor
   cannot capture yield they did not earn by depositing right before a distribution and leaving right
   after. Long-term stakers are not diluted by just-in-time capital.
4. **No free value.** A user can never redeem more than they deposited (`redeem(deposit(a)) <= a`).

> These four promises are the spec. The audit (and `pact intent`) should find where the code **violates
> its own stated intent**. (It does — on purpose. See the planted bugs.)
