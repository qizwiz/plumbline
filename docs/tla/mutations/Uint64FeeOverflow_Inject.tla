\* MUTATION: state_inject_with_correlation(Uint64FeeOverflow)
\* parent: Uint64FeeOverflow
\* trace_hash: ac7c83bb3786

--------------------------- MODULE Uint64FeeOverflow_Inject ---------------------------
(*
 * Formal specification of plumbline's Uint64FeeOverflow FailureMode.
 *
 * The bug class: a cumulative accounting variable is declared at a
 * width too narrow for the values it must hold. Over time, additions
 * push the accumulator past `2**width - 1` and it silently WRAPS to
 * zero (or some smaller value) without reverting. The on-chain
 * accounting now disagrees with the actual ETH balance — fees that
 * were paid in are accounting-orphaned; on Solidity 0.8+ the wrap is
 * an explicit revert (still bad — bricked withdrawal), on Solidity
 * pre-0.8 (puppy-raffle is 0.7.6) it silently wraps.
 *
 * The bug-class TLA+ shape is "monotonicity violation via truncation":
 * actual cumulative inflow grows monotonically (every fee paid in
 * increases the total), but the tracked accumulator does NOT — when
 * the accumulator hits 2**64 - 1 and one more fee comes in, the
 * accumulator's next value is SMALLER than its previous value. That
 * monotonicity violation IS the bug.
 *
 * Concrete instance: Cyfrin puppy-raffle H-3, PuppyRaffle::totalFees.
 * `uint64 public totalFees`. Cumulative raffle fees (in wei) can
 * exceed `2**64 - 1` (~18.4 ETH) over enough raffles. The next fee
 * after overflow silently wraps, and `withdrawFees` thereafter
 * either pays the wrong amount or reverts on the strict balance check.
 * (See examples/puppy-raffle/.ANSWERS.md H-3.)
 *
 * Models the per-fee accounting update: actual_total grows by the fee;
 * tracked_total grows by `(fee mod 2**Width)` to model the truncation.
 * The bug surfaces as a TLC counterexample where actual_total >
 * tracked_total — i.e., the accounting forgot some fees.
 *
 * Corresponds to:
 *   examples/puppy-raffle/PuppyRaffle.sol (totalFees)
 *   examples/puppy-raffle/.ANSWERS.md (H-3)
 *
 * Architectural lineage:
 *   Distinct bug-class from SignatureReplay / ReentrancyDrain (both
 *   "should-be-one-shot but isn't"). This is "monotonicity-via-
 *   truncation" — the structural pattern transfers to any cast-down
 *   accumulator (uint128 fees, uint96 deposits, etc.) and to any
 *   silent narrowing cast in arithmetic.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config Uint64FeeOverflow.cfg -deadlock Uint64FeeOverflow
 *
 * Expected outcome: TLC reports invariant TrackedMatchesActual VIOLATED.
 * The counterexample trace is the bug: enough fees accumulate that
 * the tracked accumulator wraps and falls behind the actual cumulative
 * fee inflow.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    FeePerRaffle,        \* Scalar Nat: per-raffle fee added to the
                         \* cumulative accumulator. In the concrete
                         \* puppy-raffle this is `totalAmountCollected * 20 / 100`
                         \* for a given raffle.
    MaxValue,            \* Scalar Nat: 2**Width - 1 + 1 = 2**Width.
                         \* The accumulator wraps modulo this value.
                         \* For uint64 this would be 2**64; for the
                         \* TLC model we shrink it so the bug fires in
                         \* finite states.
    MaxRaffles,           \* Scalar Nat: bound the number of raffles to
    FRESHNESS   \* max clock steps before data is considered stale
                         \* keep the state space finite for TLC.
ASSUME FeePerRaffle \in Nat
ASSUME MaxValue     \in Nat
ASSUME MaxRaffles   \in Nat
ASSUME MaxValue > 0
ASSUME FeePerRaffle > 0
ASSUME MaxRaffles > 0

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    raffles_held,        \* Nat: number of raffles completed so far
    actual_total,        \* Nat: TRUE cumulative fees (unbounded — what
                         \* the contract balance reflects)
    tracked_total,        \* Nat: BUGGY accumulator (mod MaxValue) — what
    global_clock      \* Nat: global monotonic clock (staleness proxy)
                         \* the contract's uint64 totalFees says

vars == <<raffles_held, actual_total, tracked_total, global_clock>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ raffles_held  \in Nat
    /\ actual_total  \in Nat
    /\ tracked_total \in Nat
    /\ tracked_total < MaxValue         \* the cast-down constraint
    /\ global_clock \in Nat

(* ---------------------------------------------------------------------------
   Initial state — no raffles held, no fees accumulated
   --------------------------------------------------------------------------- *)
Init ==
    /\ raffles_held  = 0
    /\ actual_total  = 0
    /\ tracked_total = 0
    /\ global_clock = 0

(* ---------------------------------------------------------------------------
   FinishRaffleBuggy — the BUGGY accumulation step.

   Models the puppy-raffle line:
       totalFees = totalFees + uint64(fee);
   The right-hand-side addition wraps modulo 2**64. We model that by
   adding the fee to tracked_total and taking the result mod MaxValue.

   The actual_total is what the contract balance would reflect (no
   truncation in ETH transfers — wei is unbounded as far as accounting
   correctness goes).
   --------------------------------------------------------------------------- *)
FinishRaffleBuggy ==
    /\ raffles_held < MaxRaffles
    /\ raffles_held'  = raffles_held + 1
    /\ actual_total'  = actual_total + FeePerRaffle
    /\ tracked_total' = (tracked_total + FeePerRaffle) % MaxValue
    /\ UNCHANGED global_clock

(* ---------------------------------------------------------------------------
   FinishRaffleCorrect — the CORRECT accumulation step.

   The fix shape: widen the accumulator. We model "widened" by removing
   the mod — tracked grows unbounded, matching actual.
   --------------------------------------------------------------------------- *)
Tick ==
    /\ global_clock <= FRESHNESS
    /\ global_clock' = global_clock + 1
    /\ UNCHANGED <<raffles_held, actual_total, tracked_total>>

FinishRaffleCorrect ==
    /\ raffles_held < MaxRaffles
    /\ raffles_held'  = raffles_held + 1
    /\ actual_total'  = actual_total + FeePerRaffle
    /\ tracked_total' = tracked_total + FeePerRaffle    \* no mod — uint256
    /\ UNCHANGED global_clock

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)
Next ==
    \/ (FinishRaffleBuggy)
    \/ Tick

Fairness == WF_vars(FinishRaffleBuggy)

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy accumulator violates.
   =========================================================================== *)

(* The contract PROMISES: totalFees reflects every fee ever collected.
 * Concretely: tracked_total == actual_total at every point. The buggy
 * accumulation breaks this as soon as actual_total >= MaxValue. *)
TrackedMatchesActual ==
    tracked_total = actual_total

(* Weaker form: tracked_total is at most actual_total. This is true
 * (tracked = actual mod MaxValue, so tracked <= actual always) so it
 * holds even for the buggy spec — included as a sanity check that the
 * model captures the truncation direction (lose, never gain). *)
TrackedAtMostActual ==
    tracked_total <= actual_total

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* The actual cumulative grows monotonically — wei doesn't lose itself
 * just because we cast down for storage. *)
ActualMonotonic ==
    [][actual_total <= actual_total']_actual_total

(* The TRACKED cumulative SHOULD grow monotonically — and on the buggy
 * spec it doesn't (tracked' = (tracked + fee) % MaxValue can be smaller
 * than tracked when there's a wrap). TLC reports this as a violation
 * of the temporal property when wraps occur. *)
TrackedMonotonic ==
    [][tracked_total <= tracked_total']_tracked_total

StaleDataRejected ==
    actual_total > 0 => global_clock <= FRESHNESS


=============================================================================
