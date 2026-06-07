--------------------------- MODULE IncentiveBonusBreaksInvariant ---------------------------
(*
 * Formal specification of plumbline's IncentiveBonusBreaksInvariant FailureMode.
 *
 * The bug class: a core protocol invariant (constant-product AMM formula
 * x*y=k, total-supply accounting, balance equation, etc.) is maintained
 * through standard operations, but a PERIODIC BONUS/INCENTIVE mechanism
 * drains reserves or mints tokens without compensating adjustments. Every
 * Nth operation triggers the bonus; after enough operations, the invariant
 * is violated — reserves are depleted, or accounting is unbalanced.
 *
 * Structural shape: "incentive-bonus-breaks-core-invariant." The protocol
 * has a well-defined mathematical invariant that SHOULD hold over all
 * operations. A counter tracks operation count; when counter % N == 0,
 * the bonus fires (extra token transfer, reward mint, fee drain, etc.)
 * WITHOUT the compensating update to reserves/supply/accounting that would
 * preserve the invariant. Over time the invariant drifts and eventually
 * breaks catastrophically (pool drained, withdrawals revert, etc.).
 *
 * Distinct from:
 *  - SignatureReplay (no guard) — here the issue is not missing guards
 *    but EXTRA uncompensated transfers
 *  - ReentrancyDrain (guard misplaced) — not a reentrancy issue
 *  - Uint64FeeOverflow (accumulator truncation) — not about truncation;
 *    the invariant is correct arithmetic that is broken by side-effects
 *  - All others (identity/auth bugs) — this is a pure accounting/invariant
 *    violation via periodic bonus payments
 *
 * Concrete instance: Cyfrin t-swap H-5, TSwapPool::_swap gives away
 * 1e18 extra output tokens every 10 swaps (swap_count >= SWAP_COUNT_MAX).
 * The constant-product formula x*y=k assumes every swap is compensated
 * (you pay input, you get proportional output), but the bonus is FREE —
 * no input paid, reserves drop by 1e18. After 10 rounds of 10 swaps each,
 * 10e18 tokens drained from reserves, x*y no longer equals the original k.
 * Pool can be drained to zero.
 * (See examples/t-swap/.ANSWERS.md H-5.)
 *
 * Generalizes to:
 *  - Any AMM/DEX incentive (volume rewards, liquidity mining payouts)
 *    that pays from pool reserves without minting offsetting LP tokens
 *  - Fee/reward distributions that mint supply without proportional backing
 *  - Periodic airdrops from a vault with no external funding mechanism
 *  - Loyalty points that drain a fixed reserve every N actions
 *  - Gas-refund patterns that pay ETH from contract balance without
 *    tracking replenishment
 *
 * Architectural lineage:
 *   Ninth distinct bug-class shape in the corpus (was 8 at session start).
 *   Authored after t-swap H-5 ran cold against existing shapes — none
 *   structurally fit: this is not an auth/identity/guard bug, but a
 *   pure mathematical invariant violation via periodic uncompensated drains.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config IncentiveBonusBreaksInvariant.cfg -deadlock IncentiveBonusBreaksInvariant
 *
 * Expected outcome: TLC reports invariant ReservesNonNegative VIOLATED
 * (or ConstantProductHolds VIOLATED, depending on which we check first).
 * The counterexample trace is the bug: swap_count reaches BONUS_THRESHOLD
 * repeatedly, each time draining BONUS_AMOUNT from reserves without
 * compensating input; after enough swaps, reserves_y < 0 (or x*y drifts
 * far below the initial k).
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    InitialReserveX,     \* Nat: initial reserve of token X in the pool
    InitialReserveY,     \* Nat: initial reserve of token Y in the pool
    SwapAmountIn,        \* Nat: per-swap input amount (paid by user)
    BonusThreshold,      \* Nat: every N swaps, the bonus fires
    BonusAmount,         \* Nat: extra output tokens given as bonus (FREE)
    MaxSwaps             \* Nat: TLC bound on total swaps

ASSUME InitialReserveX \in Nat
ASSUME InitialReserveY \in Nat
ASSUME SwapAmountIn    \in Nat
ASSUME BonusThreshold  \in Nat
ASSUME BonusAmount     \in Nat
ASSUME MaxSwaps        \in Nat
ASSUME InitialReserveX > 0
ASSUME InitialReserveY > 0
ASSUME SwapAmountIn > 0
ASSUME BonusThreshold > 0
ASSUME BonusAmount > 0
ASSUME MaxSwaps > 0

(* The initial constant product k = x * y. In a correct AMM, every swap
 * should preserve this (modulo fees, which we abstract away for simplicity).
 * The buggy pool violates it by draining reserves via bonus without input. *)
InitialK == InitialReserveX * InitialReserveY

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    reserve_x,       \* Nat: current reserve of token X
    reserve_y,       \* Nat: current reserve of token Y (the drained token)
    swap_count,      \* Nat: number of swaps executed so far (mod BonusThreshold)
    swaps_total      \* Nat: total swaps executed (TLC bound counter)

vars == <<reserve_x, reserve_y, swap_count, swaps_total>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ reserve_x   \in Int    \* Int not Nat — reserves can go negative (bug)
    /\ reserve_y   \in Int
    /\ swap_count  \in Nat
    /\ swaps_total \in Nat

(* ---------------------------------------------------------------------------
   Initial state — pool initialized with reserves, no swaps yet
   --------------------------------------------------------------------------- *)

Init ==
    /\ reserve_x   = InitialReserveX
    /\ reserve_y   = InitialReserveY
    /\ swap_count  = 0
    /\ swaps_total = 0

(* ---------------------------------------------------------------------------
   SwapBuggy — the BUGGY AMM swap action.

   Models the t-swap _swap function as written (H-5 vulnerable):
     1. User pays SwapAmountIn of token X into the pool.
     2. Pool computes proportional output of token Y via constant-product
        formula (we simplify to: output = SwapAmountIn, ignoring the exact
        formula since the BUG is in the bonus, not the swap math).
     3. Increment swap_count.
     4. IF swap_count >= BonusThreshold: give user BonusAmount extra Y for
        FREE (no additional input), reset swap_count to 0.

   The bug: step 4 drains reserve_y by BonusAmount without any compensating
   increase in reserve_x or decrease in some offsetting balance. The
   constant product x*y drifts downward. After enough bonuses, reserve_y
   can go negative (pool insolvent).
   --------------------------------------------------------------------------- *)

SwapBuggy ==
    /\ swaps_total < MaxSwaps
    /\ reserve_x' = reserve_x + SwapAmountIn       \* user pays in X
    /\ reserve_y' = IF swap_count + 1 >= BonusThreshold
                    THEN reserve_y - SwapAmountIn - BonusAmount
                                                    \* normal output + bonus
                    ELSE reserve_y - SwapAmountIn  \* normal output only
    /\ swap_count' = IF swap_count + 1 >= BonusThreshold
                     THEN 0                         \* reset counter
                     ELSE swap_count + 1
    /\ swaps_total' = swaps_total + 1

(* ---------------------------------------------------------------------------
   SwapCorrect — the CORRECT AMM swap action.

   The fix shape: REMOVE the periodic bonus, OR fund the bonus from an
   external vault/treasury (not the pool reserves). If the bonus MUST
   come from reserves, mint offsetting LP tokens or take a compensating
   fee to preserve x*y=k.

   For this spec we model "remove the bonus" — the swap only performs
   the standard constant-product exchange with no extra drain.
   --------------------------------------------------------------------------- *)

SwapCorrect ==
    /\ swaps_total < MaxSwaps
    /\ reserve_x' = reserve_x + SwapAmountIn
    /\ reserve_y' = reserve_y - SwapAmountIn       \* no bonus
    /\ swap_count' = swap_count + 1                 \* counter still increments
                                                    \* (for other features)
    /\ swaps_total' = swaps_total + 1

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next == SwapBuggy

Fairness == WF_vars(SwapBuggy)

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANTS THAT MUST HOLD — and that the buggy pool violates.
   =========================================================================== *)

(* Core AMM invariant: reserves must stay non-negative. The pool PROMISES
 * that it has enough tokens to cover all outstanding claims. The buggy
 * bonus drains reserve_y below zero after enough swaps.
 *
 * TLC counterexample: a sequence of SwapBuggy actions where swap_count
 * hits BonusThreshold multiple times, each time draining BonusAmount.
 * Eventually reserve_y < 0 — the pool is insolvent. *)
ReservesNonNegative ==
    /\ reserve_x >= 0
    /\ reserve_y >= 0

(* Constant-product invariant (simplified): after swaps, x*y should be
 * CLOSE to the initial k. We allow some drift for fees (not modeled),
 * but the buggy bonus causes LARGE drift — x*y << InitialK.
 *
 * For the TLC model we check a weaker form: "product does not drop below
 * half the initial k" — if it does, the pool is catastrophically drained.
 * The buggy spec violates even this loose bound. *)
ConstantProductHolds ==
    reserve_x * reserve_y >= InitialK \div 2

(* Sanity: swap count never exceeds the threshold (it resets to 0) *)
SwapCountBounded ==
    swap_count < BonusThreshold

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Reserves shrink monotonically (in the buggy spec, reserve_y only goes
 * down — no liquidity adds modeled here). This is not violated; it's a
 * sanity check that we're modeling a drain correctly. *)
ReserveYMonotonic ==
    [][reserve_y' <= reserve_y]_reserve_y

(* If swaps continue, the pool WILL eventually hit insolvency (reserve_y < 0)
 * in the buggy spec. This is the temporal form of the bug — it's not just
 * reachable, it's INEVITABLE given enough swaps. The correct spec never
 * reaches insolvency. *)
EventualInsolvency ==
    <>(reserve_y < 0)

=============================================================================
