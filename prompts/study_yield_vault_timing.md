# Study note — yield-vault timing attacks (the dreUSDs #0 priority)

dreUSDs is a yield-bearing ERC-4626 vault (stake dreUSD → earn "real yield, paid daily"). That's the
sDAI / Ethena-sUSDe model. The #0 bug class is **yield-timing / JIT sniping**. Learn the *correct*
design here so you recognize the deviation on sight Jun 8.

## How a yield vault works
Stake the stablecoin → get shares. Yield enters by **raising `totalAssets()` WITHOUT minting shares**,
so price-per-share (`assets/shares`) rises and every holder appreciates. The entire security question
is: **how fast does that price rise when yield arrives?**

- **Instant lump (VULNERABLE):** yield is `transfer`'d into the vault in one tx → `totalAssets()` jumps
  → share price jumps in a single block.
- **Streamed/vested (SAFE):** yield is released *gradually* over a window; `totalAssets()` subtracts the
  still-unvested portion, so price rises smoothly per-second.

## The attack — JIT (just-in-time) yield sniping
If the price jumps instantly (or vests too fast / predictably), an attacker:
1. watches for the **daily** yield injection (predictable "paid daily" makes this trivial),
2. **deposits a large amount right before** it,
3. **withdraws right after** → captures a pro-rata slice of that day's yield that *long-term stakers
   actually earned*. Pure theft, repeatable daily.

**This is a value-creation invariant break** — and plumbline tests it directly:
`deposit(a) → [inject the daily yield] → redeem(shares) > a ?` → if profitable, JIT works.

## The two mitigations (find whether dreUSDs has EITHER)
1. **Vesting / streaming** (Ethena sUSDe): `transferInRewards(amount)` starts a linear vest over a
   `VESTING_PERIOD` (sUSDe ≈ 8h); `totalAssets() = asset.balanceOf(this) - getUnvestedAmount()`. A JIT
   depositor only earns the sliver that vests during their stay. **Check: does dreUSDs' `totalAssets()`
   subtract an unvested amount, or just return `dreUSD.balanceOf(vault)`?** The latter = lumpy = finding.
2. **Withdrawal cooldown / lockup** (sUSDe V2: `cooldownShares` + `cooldownDuration`): you can't
   deposit-and-instantly-exit, killing the sandwich. **Check: can you deposit and withdraw in the same
   tx / same block / same day?** No cooldown + lumpy yield = JIT is wide open.

If dreUSDs has **neither vesting nor cooldown** and yield arrives as a lump → that's likely your
Medium/High right there.

## Adjacent timing/accounting bugs to check while you're in there
- **Vesting gameable:** can a *new* `transferInRewards` reset the vest clock to re-lock or grief? Off-by-one
  in `getUnvestedAmount`? Can the unvested be claimed early?
- **Zero-supply / first-staker:** yield injected when `totalSupply == 0` (÷0 or stuck/lost yield).
- **Donation:** anyone `transfer`s dreUSD straight to the vault to bump share price (donation inflation
  on top of the yield path).
- **Rounding direction** on the daily accrual (in the protocol's favor, both deposit & withdraw).
- **Decimals** in the yield math (USDC 6 vs dreUSD 18) — see playbook §2.

## Reference implementations to read (the "right answer")
- **Ethena `StakedUSDe` / `StakedUSDeV2`** — `transferInRewards`, `getUnvestedAmount`, `VESTING_PERIOD`,
  the V2 cooldown. THE canonical sample; read it first, it's exactly this shape.
- **MakerDAO sDAI / DSR `Pot`** — `chi`/`dsr`/`drip` continuous per-second accrual (the no-lump approach).
- **OpenZeppelin `ERC4626`** — base + virtual-shares inflation mitigation.

## Plumbline JIT test (parameterized — fill the real names Jun 8, then run)

The JIT bug IS a value-creation invariant break, so plumbline can test it autonomously. Replace the
`/*FILL*/` names with dreUSDs' real functions once the code drops; the concrete-replay validator then
confirms any "profit" is real (not a halmos nonlinear artifact).

```solidity
// JIT yield-sniping test: can an attacker deposit, capture an instant yield drop, and exit at a profit?
// c = dreUSDs vault; dre = dreUSD stablecoin; both funded to address(this) by the scaffold.
function check_inv(uint256 a, uint256 y) public {
    require(a > 0 && a <= 1e24);
    require(y > 0 && y <= 1e24);

    // (optional) a pre-existing long-term staker so JIT steals from someone:
    // c./*deposit*/(seed, address(0xBEEF));

    uint256 sh   = c./*deposit*/(a, address(this));   // attacker stakes RIGHT BEFORE the yield drop
    dre./*transfer or yield-inject*/(address(c), y);   // the daily yield hits the vault as a lump
    uint256 out  = c./*redeem*/(sh, address(this), address(this)); // attacker exits RIGHT AFTER

    // FAITHFUL invariant: a just-in-time depositor must NOT extract more than they put in.
    // If `out > a`, the lump-sum yield was snipable -> JIT works -> FINDING.
    assert(out <= a);
}
```

If dreUSDs **streams/vests** yield (totalAssets subtracts unvested) or has a **withdrawal cooldown**,
this PROVES (out <= a) — good, the vault is safe. If it injects a lump with no cooldown, halmos returns
a counterexample (`y > 0` profit), the replay validator confirms it concretely → your Medium/High.
(Caveat: if the real yield-injection is a permissioned function, model the attacker as also being able
to front-run/sandwich the keeper's injection tx, or test with the injection as a separate actor.)

## First 30 minutes on Jun 8 (yield vault)
1. Open dreUSDs' `totalAssets()` → unvested-subtracting, or raw balance? (raw = lumpy = dig in)
2. Find where daily yield is injected → vesting function or plain `transfer`?
3. Is there a **withdrawal cooldown/lockup**? deposit+withdraw same block possible?
4. Is the injection permissionless / front-runnable / predictably timed?
5. If lumpy + no cooldown → build the plumbline JIT test (deposit → inject → redeem > deposit?) and
   write it up.
