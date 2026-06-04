# Audit playbook — stablecoin + ERC-4626 vault + mint/redeem/rewards + OFT

Scope shape: a USD-pegged stablecoin (1:1 backed/redeemable) with an ERC-4626 share vault, on-chain
mint/redemption, rewards distribution, and a LayerZero OFT cross-chain adapter. (Tuned for Sherlock
#1259 dreUSD, but general to this shape.) Doubles as: (a) a manual checklist, (b) the hypothesis menu
fed to the adaptive planner as `context`. Each item = the invariant that must hold + the attack that
breaks it. ★ = plumbline's sweet spot (conservation/solvency, auto-checkable); ☉ = manual-heavy.

## CONFIRMED protocol model (dre.mortgage, from their site + scope)

dreUSD = USD stablecoin (1:1 USDC, backed by REAL-ESTATE CREDIT / RWA). dreUSDs = ERC-4626 vault you
stake dreUSD into to earn the yield — "REAL YIELD. PAID DAILY." Structurally an sDAI / Ethena-sUSDe
yield-vault. Backing is OFF-CHAIN RWA → its onchain value is likely admin-attested (a trust
assumption to note, AND a manipulation surface to probe).

**SHARPENED PRIORITY for THIS protocol (hunt in this order):**
0. **★★ JIT YIELD SNIPING (the headline risk for a "paid daily" vault):** if the daily reward hits the
   vault as an INSTANT LUMP (raises share price in one tx), an attacker deposits right before it,
   captures yield long-term stakers earned, and withdraws. Find HOW rewards are injected: instant lump
   = finding (Medium/High); streamed/vested over time = mitigated. Plumbline test: deposit → inject
   reward → redeem → profit? = value-creation invariant broken.
1. DECIMALS (USDC 6 vs dreUSD/shares 18) — §2, highest-frequency.
2. ERC-4626 inflation/donation — §1.
3. Rewards-distribution accounting (the daily accrual math) — §3.
4. Mint/redeem 1:1 + backing solvency, and the RWA attestation/oracle trust surface — §2.
5. LayerZero OFT cross-chain supply conservation — §4 (manual).

## 1. ERC-4626 vault (the share token)  ★
- **No value creation (round-trip):** `redeem(deposit(a)) <= a`. Break: rounding in the user's favor.
- **Solvency:** shares issued never exceed backing — `convertToAssets(totalSupply) <= totalAssets()`.
- **First-depositor / donation inflation:** attacker mints 1 wei share, donates assets to inflate
  price, victim's deposit rounds to 0 shares. Check the mitigation (virtual shares / dead shares /
  `_decimalsOffset`) actually exists and is sufficient.
- **Rounding direction:** deposit→shares rounds DOWN, withdraw→assets rounds DOWN (protocol-favorable).
  Any round-UP in the user's favor is a leak.

## 2. Stablecoin mint / redeem (dreUSD ↔ USDC, 1:1)  ★
- **Backing conservation (the big one):** `dreUSD.totalSupply() <= backingHeld` — you can never mint
  dreUSD that isn't backed. Break: a mint path that skips/under-counts the USDC pull-in.
- **Peg round-trip:** `redeem(mint(x)) <= x` (no free value through mint→redeem), and `mint(x) == x`
  net of declared fees.
- **★★ DECIMALS (highest-yield bug here):** USDC = **6 decimals**, dreUSD/shares likely **18**. Every
  conversion (mint, redeem, convert, fee) is a decimals landmine — off-by-1e12 mints free value or
  bricks redemptions. Check *every* scaling expression.
- **Access control on mint:** only authorized minter can create unbacked supply; no public mint.
- **Reentrancy:** mint/redeem touching token callbacks (USDC is not callback-y, but a malicious
  fee/recipient hook could be) — state updated before external calls?
- **Fee rounding:** a fee that rounds to 0 on small amounts, or rounds in the user's favor, drains.

## 3. Rewards distribution  ★ (accounting) / ☉ (timing)
- **Conservation:** `sum(claimable) <= rewardsFunded`. Break: accumulator/`rewardPerToken` overflow or
  zero-supply division.
- **No principal-as-rewards:** claiming rewards can't withdraw backing/principal.
- **No double-claim; rewardDebt correctness** (MasterChef class): does balance change update reward
  debt before/after correctly? Stake→claim→unstake→restake sequences.
- **First/zero-supply reward division** (÷ totalSupply == 0).

## 4. LayerZero OFT adapter  ☉ (cross-chain — manual-heavy; plumbline weak here)
- **Supply conservation:** burn on source == mint on destination; total cross-chain supply constant.
- **Shared decimals / dust:** OFT `sharedDecimals` truncation — does dust get lost or duplicated?
- **Peer/trusted-remote config; message replay; slippage** on the bridged amount.

## Ready harness skeletons (fill the real names on Jun 8, then `pact_check`)

Each is a `check_inv` body; the adaptive planner emits the deploy/scaffold. Faithful, gated by
concrete-replay (a finding only counts if the assert reverts on the cex).

```solidity
// T1 — vault no-value-creation (deposit then redeem yields no more than deposited)
require(a > 0 && a <= 1e30);
uint256 sh = c.deposit(a, address(this));
assert(c.redeem(sh, address(this), address(this)) <= a);

// T2 — stablecoin mint/redeem round-trip (no free value through the peg)
require(a > 0 && a <= 1e24);          // USDC units (6dp) — mind decimals
uint256 minted = c.mint(a);           // dreUSD out for `a` USDC in
assert(c.redeem(minted) <= a);        // can't extract more USDC than deposited

// T3 — backing solvency (total stablecoin supply never exceeds backing held)
// drive a mint, then assert the global invariant:
c.mint(a);
assert(dreUSD.totalSupply() <= usdc.balanceOf(address(c)) /*+ other tracked backing*/);
```

## Pre-contest study (the 4 days) — pattern-load on the real class

dreUSD's own docs aren't public (drefinance → "Rezerve", a different protocol); architecture arrives
with the code Jun 8. So study the CLASS until you recognize it on sight.

**Best primers (read these first):**
- Zellic — "Exploring ERC-4626: A Security Primer" (zellic.io/blog) — the single best overview.
- Arbitrary Execution — "Vulnerabilities of ERC-4626 Vaults, Part 2" (arbitraryexecution.com/blog).
- RivaNorth — "ERC-4626 Vulnerabilities and How to Avoid Them" (checklist style).

**Real findings to internalize (pattern → lesson):**
- **DECIMALS** — code-423n4/2024-04-noya #1438: TVL recorded at 18 decimals not scaled to USDC's 6 →
  off by 1e12 → accounting broken. *Lesson:* trace EVERY scale between USDC(6) and dreUSD/shares(18).
- **ROUNDING DIRECTION** — code-423n4/2022-11-redactedcartel #197: `previewWithdraw` must round UP, but
  it called `convertToShares` (rounds down) → returns too-low → value leaks to the user. *Lesson:*
  verify every preview*/convert* rounds in the PROTOCOL's favor, both directions.
- **INFLATION / donation** — sherlock 2024-01-napier #125, pareto #72, smilee #22: first-depositor
  donates to inflate share price; later deposits round to 0 shares. *Lesson:* prove the mitigation
  (virtual/dead shares) exists AND is sized to defeat a realistic donation.

## Day-1 procedure (Jun 8)
1. Clone the published scope; identify the vault, the stablecoin, the mint/redeem, the rewards module.
2. Feed this playbook to the adaptive planner as `context`; run `pact_check` on each in-scope contract
   → it surfaces candidate conservation/solvency violations, replay-validated (no false positives).
3. **Lead manual review with the DECIMALS checklist (§2)** — it's the highest-yield class and the one
   a tool + a careful human both catch. Then rewards (§3) and OFT (§4, manual).
4. Write up confirmed findings; submit before Jun 17. Even one Low/Info pays into the pool + is portfolio.
