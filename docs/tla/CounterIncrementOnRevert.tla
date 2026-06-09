----------------------- MODULE CounterIncrementOnRevert -----------------------
(*
 * Formal specification of plumbline's CounterIncrementOnRevert FailureMode.
 *
 * The bug class: a usage-tracking counter is incremented for EVERY call
 * attempt — including calls that fail (revert / fall through to fallback) —
 * rather than only for calls that succeed. The counter thereby overstates
 * the amount of resource (value, gas, quota) genuinely consumed, prematurely
 * exhausting a session budget that should still have capacity.
 *
 * Structural shape: "state mutation before guard discharge." The increment
 * is unconditional; it appears before (or regardless of) the success check
 * on the inner call. When the inner call reverts, the counter stays
 * incremented. The session believes it has spent what was never consumed.
 *
 * Concrete instance: Code4rena/Cantina sequence-v3 audit L-02.
 * `ExplicitSessionManager` increments the per-session value-spent counter
 * for fallback and reverted calls, prematurely exhausting session budgets.
 * (See examples/sequence/.ANSWERS.md L-02.)
 *
 * Invariant violated: spent = actual_used.
 * A session's spent counter must equal the value genuinely consumed by
 * successful calls. The buggy increment leaves spent > actual_used after
 * any reverted call, and budget exhaustion can be reached before any real
 * value changes hands.
 *
 * Models a single session with a fixed Budget. Each call costs 1 unit of
 * value. A call can succeed (OUTCOME_OK) or revert (OUTCOME_REVERT). The
 * buggy manager increments `spent` unconditionally; the correct manager
 * increments only on OUTCOME_OK.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
 *     -config CounterIncrementOnRevert.cfg -deadlock CounterIncrementOnRevert
 *
 * Expected outcome: TLC reports invariant BudgetReflectsActualUse VIOLATED.
 * Minimal counterexample (2 steps):
 *   Init: spent=0, actual_used=0
 *   BuggyCall(OUTCOME_REVERT): spent=1, actual_used=0
 *   => BudgetReflectsActualUse = (1 = 0) => FALSE
 *)

EXTENDS Integers, TLC

(* ---------------------------------------------------------------------------
   Constants — smallest model that triggers the bug
   --------------------------------------------------------------------------- *)

CONSTANTS
    Budget,    \* max value the session permits (positive integer)
    MaxSteps   \* TLC bound on total call attempts

ASSUME Budget   \in Nat /\ Budget   > 0
ASSUME MaxSteps \in Nat /\ MaxSteps > 0

OUTCOME_OK     == "ok"
OUTCOME_REVERT == "revert"
Outcomes       == {OUTCOME_OK, OUTCOME_REVERT}

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    spent,       \* Nat: counter of value "charged" to the session (buggy)
    actual_used, \* Nat: value genuinely consumed by successful calls
    steps        \* Nat: TLC step bound

vars == <<spent, actual_used, steps>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ spent       \in Nat
    /\ actual_used \in Nat
    /\ steps       \in Nat

(* ---------------------------------------------------------------------------
   Initial state — session starts with zero usage
   --------------------------------------------------------------------------- *)

Init ==
    /\ spent       = 0
    /\ actual_used = 0
    /\ steps       = 0

(* ---------------------------------------------------------------------------
   BuggyCall(outcome) — models ExplicitSessionManager's buggy executeCall().

   The buggy code increments the value-usage counter BEFORE (or regardless
   of) the inner call's success. Whether outcome = OUTCOME_REVERT or
   OUTCOME_OK, `spent` is incremented. Only on OUTCOME_OK does actual_used
   increase — reflecting that no value changed hands on a revert.

   Guard: the session must still have remaining budget (spent < Budget).
   In the buggy system this guard uses the already-inflated `spent`, so the
   session becomes "exhausted" prematurely.
   --------------------------------------------------------------------------- *)

BuggyCall(outcome) ==
    /\ outcome \in Outcomes
    /\ steps   < MaxSteps
    /\ spent   < Budget                          \* session is still open
    /\ spent'       = spent + 1                  \* BUG: unconditional increment
    /\ actual_used' = IF outcome = OUTCOME_OK
                      THEN actual_used + 1
                      ELSE actual_used
    /\ steps' = steps + 1

(* ---------------------------------------------------------------------------
   State machine — any call with any outcome, bounded by MaxSteps
   --------------------------------------------------------------------------- *)

Next == \E outcome \in Outcomes : BuggyCall(outcome)

Spec == Init /\ [][Next]_vars

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy counter violates.
   ===========================================================================

 * The session manager PROMISES: the amount charged to the session equals
 * the value actually consumed by successful operations.
 *
 * BudgetReflectsActualUse: spent = actual_used
 *
 * The buggy BuggyCall(OUTCOME_REVERT) action leaves spent = actual_used + 1,
 * immediately violating this invariant. TLC finds the counterexample in
 * one step from Init when MaxSteps >= 1 and Budget >= 1.
 *)

BudgetReflectsActualUse ==
    spent = actual_used

(* Weaker form: session declared exhausted only when genuinely exhausted.
   This is the property that matters to callers of the session. *)
ExhaustionIsHonest ==
    spent >= Budget => actual_used >= Budget

(* ---------------------------------------------------------------------------
   Structural invariants (always hold, help confirm model correctness)
   --------------------------------------------------------------------------- *)

SpentNeverExceedsBudgetPlusOne ==
    spent <= Budget   \* enforced by the session guard

SpentDominatesActual ==
    spent >= actual_used   \* always true in the buggy model

=============================================================================
