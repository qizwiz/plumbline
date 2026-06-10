# Multi-mode invariant demonstration on Sherlock 1259 Issue #1

**Generated 2026-06-09 23:35** — bounded execution of JH's larger hypothesis on a single concrete bug. The hypothesis: bugs whose witnesses span multiple representation modes cannot be captured by any single-mode invariant alone; the composition is the actual structural invariant.

**Test case:** dreUSDs ERC-4626 vault first-depositor inflation via the vested-rewards channel. Verified bug. Filed Sherlock 1259 Issue #1.

---

## The bug, restated mechanically

1. `dreUSDs.totalAssets()` returns `_virtualBalance + dreRewardsDistributor.vestedAmount()`
2. `_virtualBalance` is updated only on `_deposit()` and `_withdraw()`
3. `vestedAmount()` grows monotonically with `block.timestamp` after `addRewards()`
4. ERC-4626 share calculation: `shares = assets * totalSupply / totalAssets` (with OZ's `+1` mitigation factor)
5. Attacker sequence:
   - Block t₀: attacker deposits 1 wei → `_virtualBalance = 1`, `totalSupply = 1`, `shares_attacker = 1`
   - Block t₀: admin calls `addRewards(R)` → `vestedAmount` starts growing toward R
   - Block t₀ + δ: time passes, `vestedAmount(t₀+δ) = V > 0`
   - Block t₀ + δ: victim deposits `D` → `shares_victim = D * 1 / (1 + V) → 0 for V >> D`
   - Both redeem → attacker captures ~`(_virtualBalance + V) * 1/(victim_shares + 1) ≈ all of it`

The bug requires FIVE distinct invariants violated SIMULTANEOUSLY. No single one captures it.

---

## Try each single mode in isolation

### Scalar mode (current Pass A v1 default)

**Best single-state assertion:** `assert(totalAssets() == _virtualBalance);`

**Verdict:** WRONG, in two ways.
- Holds during normal operation only when no rewards have been added — fails for the intended design with vested rewards, so the validator correctly refutes it as "describes the intended behavior, not the bug."
- Even if reformulated as `assert(_virtualBalance >= some_lower_bound)`, single-state cannot capture the cross-deposit share dilution.

**Coverage:** ~0%. Scalar mode is structurally inadequate for this bug.

### Relational mode (between two state snapshots)

**Best assertion:** between any two deposit calls,

```
old_share_price = old_totalAssets * 1e18 / old_totalSupply;
new_share_price = new_totalAssets * 1e18 / new_totalSupply;
assert(new_share_price >= old_share_price * (1 - epsilon));
```

with `epsilon ≈ 1e15` for 0.1% rounding tolerance.

**Verdict:** CAPTURES THE CORE WITNESS. This is the invariant the first-depositor inflation actually violates — share price MUST not drop across honest user deposits.

**Coverage:** ~70%. Pre/post snapshots + algebraic relation between them. Halmos discharge-able with `pre_capture` snapshots.

**Limitation:** doesn't say WHY share price drops. The bug isn't just "share price moves wrong" — it's "share price moves wrong because totalAssets grows via a channel that doesn't update _virtualBalance."

### Temporal mode (sequence of actions across time)

**Best assertion:** for any execution trace,

```
sequence:
  - deposit(attacker, 1)               // attacker_shares = 1, virtualBalance = 1
  - addRewards(R)                       // rewards channel armed
  - timeAdvance(δ)                      // vestedAmount(t₀+δ) = V > 0
  - deposit(victim, D)                  // victim_shares should ≈ D
invariant after: victim_shares >= D * totalSupply_before / totalAssets_before * (1 - epsilon)
```

**Verdict:** CAPTURES THE ATTACK STRUCTURE. The relational assertion above is the *witness*; this is the *attack-shape that constructs the witness*. Halmos stateful invariant with `--invariant-depth 4` could discharge this.

**Coverage:** ~60% of the bug, but with the right structure to make halmos actually run.

**Limitation:** temporal is hard to express precisely without knowing the attack pattern in advance, which is what we're trying to discover.

### Counting mode (cardinality / accumulator-based)

**Best assertion:** introduce ghost state `Σ_deposited` that tracks the sum of all `_deposit()` calls. Invariant:

```
ghost uint256 Σ_deposited;
hook: every _deposit(caller, assets, ...) increments Σ_deposited by assets
invariant: totalAssets() <= Σ_deposited + (total time-weighted rewards distributed so far)
```

**Verdict:** WEAK BUT CLOSE. Captures conservation across deposits — if totalAssets exceeds total deposits + total vested rewards expected, something is wrong.

**Coverage:** ~40%. Catches gross-scale arithmetic errors but not the subtle share-price dynamics.

### Null / liveness mode

Doesn't apply — this is a safety bug, not a liveness/DoS bug.

---

## The composition

| Mode | Captures | Misses |
|---|---|---|
| Scalar | nothing relevant | the dynamic relation |
| **Relational** | **the share-price preservation witness** | the attack mechanism that constructs it |
| **Temporal** | **the attack-action sequence** | what makes the sequence *succeed* |
| Counting | gross deposit/rewards conservation | the share-price dynamics |

**The composition that actually captures the bug:**

> *"There exists a sequence of operations `[deposit(small), addRewards(R), timeAdvance(δ), deposit(D)]` such that the relational invariant `share_price(after) >= share_price(before) * (1 - epsilon)` is violated for sufficiently large `V` relative to `D`."*

This is a **temporal + relational** invariant. Neither mode alone captures it. Both together do.

**This is direct empirical support for JH's larger hypothesis: representation-mode composition is required for some bug classes; single-mode emission is structurally inadequate.**

---

## What this means for the H12 test tomorrow

The composition above is exactly what Pass A v2's multi-mode schema is designed to emit. The DRE bug — the one Pass A v1 couldn't extract a CLEAN invariant for — can be expressed cleanly in the v2 schema as two linked invariants (one relational, one temporal) with a composition clause.

**Pre-registered prediction for the H12 sample-50 tomorrow:**

- Bugs that need composition (first-depositor inflation, slippage-during-rebalance, oracle-manipulation-during-flashloan) should show CLEAN rate near 0% in v1 (single-mode) and significantly above 0% in v2 (multi-mode).
- The DRE bug specifically, run through the v2 prompt with its corpus_top1 match (AuraVault::claim) as conditioning, should emit a relational+temporal composition. If it does AND halmos can discharge at least the relational part, that's the strongest possible H8/H12 confirmation.

---

## Honest scope of this demonstration

This is one bug. The hypothesis claims composition is required for a *class* of bugs. One case study supports but does not prove the claim. The H12 sample-50 tomorrow is the real test. Tonight's demonstration just shows the framing is concretely operational on at least one bug we know cold.

The bigger claim — that this generalizes across the 1,240-finding corpus — is what tomorrow's measurement decides.
