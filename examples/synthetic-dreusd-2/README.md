# dreVault (synthetic) — yield vault, withdrawal queue

`dreVault` is an ERC4626-style yield vault for dreUSD. Shares (`dreUSDs`) represent a claim on the
underlying dreUSD held by the vault. Yield is delivered by an external distributor transferring dreUSD
into the vault over time, lifting price-per-share for all holders.

Because large redemptions are serviced from an external liquidity buffer, redemption is **two-step**:
1. `requestRedeem(shares)` — burns the caller's shares immediately and records the dreUSD they are owed.
2. `claim()` — after the buffer is funded, transfers the owed dreUSD out to the caller.

## Guarantees the protocol promises

- **G1 — round-trip.** `deposit(x)` immediately followed by `requestRedeem`+`claim` returns `x` dreUSD
  (no value created or destroyed by the round trip itself).
- **G2 — redemption isolation.** One holder requesting or claiming a redemption MUST NOT change the
  price-per-share that *other* holders experience. A withdrawal is not a donation.
- **G3 — honest accounting.** `totalAssets()` reflects only the dreUSD economically owned by *current*
  shareholders — assets already committed to a pending withdrawal belong to the exiting holder, not to
  the remaining pool.
- **G4 — yield monotonicity.** Absent new deposits/withdrawals, price-per-share only moves when the
  distributor adds yield; ordinary protocol operations never move it.
