----------------------- MODULE CumulativeStateDrift -----------------------
(*
 * Formal specification of plumbline's CumulativeStateDrift FailureMode.
 *
 * The bug class: a per-call permission validator checks each call's
 * requested amount against a STALE snapshot of the cumulative accumulator
 * rather than against the truly current running total. Individual calls
 * each appear within-limit at check time, but the real cumulative sum
 * exceeds the session limit undetected.
 *
 * Structural shape: "wrong-accumulator-state in interval arithmetic."
 * The guard exists and fires correctly in isolation. The error is that
 * `check_base` — the accumulator value used in the guard — is the value
 * from an earlier point in time (e.g., session start), not the value
 * after all previously-approved calls have been applied. The invariant
 * that "cumulative spending never exceeds the per-period limit" is
 * therefore checkable only AFTER all calls complete, but the per-call
 * guard that was supposed to prevent the violation silently succeeds.
 *
 * Distinct from:
 *  - CounterIncrementOnRevert (counter advances even on failure — here
 *    all calls succeed; the error is which accumulator state is read)
 *  - ReentrancyDrain (re-entrant calls re-enter before state settles —
 *    here there is no re-entry; the issue is a stale read of a
 *    non-re-entrant accumulator)
 *
 * Concrete instance: Cantina sequence-v3 L-01.
 * PermissionValidator.validateCallPermission uses a snapshot of the
 * cumulative parameter value captured at session creation rather than
 * the post-previous-call value, so a sequence of calls each individually
 * within the per-call budget can violate the cumulative rule.
 * (See examples/sequence/.ANSWERS.md L-01.)
 *
 * Invariant violated: CumulativeLimitHolds == cumulative <= MaxPerPeriod
 * The buggy validator's per-call guard (`check_base + amount <= limit`)
 * always evaluates with `check_base = 0`, so ANY sequence of calls whose
 * individual amounts fit within the limit will all pass, even when their
 * running sum far exceeds the limit.
 *
 * Smallest counterexample: MaxPerPeriod = 3, MaxCalls = 2, call amounts = 2.
 *   Step 0 Init:  cumulative = 0, check_base = 0.
 *   Step 1 BuggyPermit(2): guard 0+2<=3 PASS; cumulative=2, check_base=0.
 *   Step 2 BuggyPermit(2): guard 0+2<=3 PASS; cumulative=4, check_base=0.
 *   => CumulativeLimitHolds: 4 <= 3 => FALSE
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
 *     -config CumulativeStateDrift.cfg -deadlock CumulativeStateDrift
 *
 * Expected outcome: TLC reports invariant CumulativeLimitHolds VIOLATED.
 *)

EXTENDS Integers, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    MaxPerPeriod, \* Nat: cumulative limit the validator is supposed to enforce
    MaxCalls      \* Nat: TLC bound on call sequence length

ASSUME MaxPerPeriod \in Nat /\ MaxPerPeriod > 0
ASSUME MaxCalls     \in Nat /\ MaxCalls     > 0

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    cumulative,  \* Nat: true running total of all approved amounts
    check_base,  \* Nat: accumulator snapshot used in per-call guard (buggy: stale)
    calls        \* Nat: step counter

vars == <<cumulative, check_base, calls>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ cumulative \in Nat
    /\ check_base \in Nat
    /\ calls      \in Nat

(* ---------------------------------------------------------------------------
   Initial state — session starts with zero usage
   --------------------------------------------------------------------------- *)

Init ==
    /\ cumulative = 0
    /\ check_base = 0
    /\ calls      = 0

(* ---------------------------------------------------------------------------
   BuggyPermit(amount) — models PermissionValidator's validateCallPermission.

   The buggy validator checks `check_base + amount <= MaxPerPeriod` where
   `check_base` is the cumulative snapshot from session creation (stuck at 0).
   On approval, the validator advances the TRUE accumulator `cumulative`
   but does NOT update `check_base`. Each subsequent call therefore sees
   the same stale baseline and the guard never reflects previously-approved
   spend.

   A correct implementation would set `check_base' = cumulative + amount`
   (or equivalently `check_base' = check_base + amount`) so the next call
   sees the current running total.
   --------------------------------------------------------------------------- *)

BuggyPermit(amount) ==
    /\ amount \in 1..MaxPerPeriod
    /\ calls < MaxCalls
    /\ check_base + amount <= MaxPerPeriod   \* BUG: check_base never advances
    /\ cumulative' = cumulative + amount
    /\ check_base' = check_base              \* BUG: should be check_base + amount
    /\ calls'      = calls + 1

(* ---------------------------------------------------------------------------
   State machine
   --------------------------------------------------------------------------- *)

Next == \E amount \in 1..MaxPerPeriod : BuggyPermit(amount)

Spec == Init /\ [][Next]_vars

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy validator violates.
   ===========================================================================

 * CumulativeLimitHolds: cumulative <= MaxPerPeriod
 *
 * Every validator promises that the running total of approved amounts
 * never exceeds the per-period limit. The buggy per-call guard fails
 * to enforce this because `check_base` doesn't advance, allowing a
 * series of individually-approved calls to collectively exceed the limit.
 *)

CumulativeLimitHolds == cumulative <= MaxPerPeriod

(* Structural invariants — always hold, confirm model correctness *)

CheckBaseNeverExceedsLimit ==
    check_base <= MaxPerPeriod   \* trivially true since check_base stays 0

CheckBaseNeverExceedsCumulative ==
    check_base <= cumulative     \* stale base never overtakes real total

=============================================================================
