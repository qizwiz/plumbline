\* MUTATION: state_inject_with_correlation(ReentrancyDrain)
\* parent: ReentrancyDrain
\* trace_hash: 7fda1d998587

--------------------------- MODULE ReentrancyDrain_Inject ---------------------------
(*
 * Formal specification of plumbline's ReentrancyDrain FailureMode.
 *
 * The bug class: a withdraw/refund function that performs an EXTERNAL
 * CALL (sending ETH to a user-controlled address) BEFORE updating its
 * internal accounting (zeroing the user's claimable balance). A
 * malicious contract whose `receive`/`fallback` re-enters the same
 * function bypasses the accounting update — every re-entry sees the
 * stale balance, sends another payout, and drains the contract one
 * claimable-unit at a time.
 *
 * This is the canonical "Checks-Effects-Interactions" violation; the
 * fix is to swap the order: zero the slot BEFORE the external call.
 *
 * Concrete instance: Cyfrin puppy-raffle H-1, PuppyRaffle::refund.
 * `refund` does `payable(msg.sender).sendValue(ticketPrice)` before
 * `players[playerIndex] = address(0)`. An attacker whose `receive`
 * calls `refund(playerIndex)` again repeats indefinitely.
 * (See examples/puppy-raffle/.ANSWERS.md H-1.)
 *
 * Models the lifecycle of one entry: registered → refunded once → slot
 * cleared. The bug surfaces as a TLC counterexample where the same
 * entry's claimable is paid out multiple times because the slot-clear
 * happens AFTER the external call, and an attacker re-entered between
 * the call and the clear.
 *
 * Corresponds to:
 *   examples/puppy-raffle/PuppyRaffle.sol (refund)
 *   examples/puppy-raffle/.ANSWERS.md (H-1)
 *
 * Architectural lineage:
 *   Patterned after plumbline/docs/tla/SignatureReplay.tla — both are
 *   "should-be-one-shot but isn't" bugs, structurally identical at the
 *   TLA+ level. The DIFFERENCE is mechanism: SignatureReplay has no
 *   nonce at all, ReentrancyDrain has a one-shot guard placed AFTER
 *   the external call (so the guard is bypassable mid-call). Both
 *   yield "paid more than authorized" counterexamples; the bug-class
 *   distinction matters for which Solidity fix shape applies (add
 *   nonce vs. reorder to CEI / add reentrancy guard).
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config ReentrancyDrain.cfg -deadlock ReentrancyDrain
 *
 * Expected outcome: TLC reports invariant ClaimedAtMostOnce VIOLATED.
 * The counterexample trace is the bug: the same entry transitions
 * Calling → Calling (re-entry) while still in the external-call window,
 * before the slot was cleared, so `paid` becomes 2.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Entries,               \* Set of registered entries, each with a fixed
                           \* claimable amount. In the concrete raffle,
                           \* each entry == one ticket holder slot.
    TicketPrice,           \* Scalar Nat: the per-entry claimable amount
                           \* (uniform — keeps cfg grammar simple, same
                           \* pattern as SignatureReplay's SigAuth).
    MaxReentries,           \* Bound on recursion depth (finite for TLC).
    FRESHNESS   \* max clock steps before data is considered stale
                           \* The bug exists for MaxReentries >= 2; the
                           \* counterexample uses exactly 2 re-entries.
ASSUME IsFiniteSet(Entries)
ASSUME TicketPrice \in Nat
ASSUME MaxReentries \in Nat
ASSUME MaxReentries >= 2     \* model needs to express at least one re-entry

\* The slot state lifecycle:
\*   "Live"    — registered, claimable, not yet refunded
\*   "Calling" — external call in flight (after balance check, before slot clear)
\*   "Cleared" — slot zeroed, no further refunds possible
\* The bug exists because the buggy spec advances Live → Calling → Cleared
\* with the slot still readable as Live during the Calling window — so a
\* re-entry inside that window sees Live again.
SlotStates == {"Live", "Calling", "Cleared"}

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    slot,         \* function Entries -> SlotStates: per-entry lifecycle
    paid,         \* function Entries -> Nat: cumulative payout per entry
    reentries,     \* function Entries -> Nat: depth of currently-nested
    global_clock      \* Nat: global monotonic clock (staleness proxy)
                  \* refund() calls on this entry (bounded by MaxReentries)

vars == <<slot, paid, reentries, global_clock>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ slot      \in [Entries -> SlotStates]
    /\ paid      \in [Entries -> Nat]
    /\ reentries \in [Entries -> Nat]
    /\ global_clock \in Nat

(* ---------------------------------------------------------------------------
   Initial state — every entry registered (Live), nothing paid, no
   in-flight refund calls.
   --------------------------------------------------------------------------- *)
Init ==
    /\ slot      = [e \in Entries |-> "Live"]
    /\ paid      = [e \in Entries |-> 0]
    /\ reentries = [e \in Entries |-> 0]
    /\ global_clock = 0

(* ---------------------------------------------------------------------------
   BUGGY refund flow — split into 3 atomic actions because the bug lives
   in the ORDER of effects:
     1. PreCheckBuggy — assert slot Live, advance to Calling, pay out
     2. ReenterBuggy  — while in Calling, attacker re-enters from receive(),
                        sees slot still Live (because step 1 advanced to
                        Calling, not Cleared), recurses
     3. PostClearBuggy — innermost call returns, slot gets cleared,
                         cascade unwinds; outer calls also clear (no-op)
   The bug: PreCheckBuggy reads slot as Live and pays — but the slot
   doesn't transition to Cleared until PostClearBuggy. Between those two
   steps the attacker can call refund again on the SAME entry; that call
   also sees Live and ALSO pays. paid[e] climbs by TicketPrice per
   re-entry.
   --------------------------------------------------------------------------- *)
PreCheckBuggy(e) ==
    /\ e \in Entries
    /\ slot[e] = "Live"                       \* the buggy read
    /\ reentries[e] < MaxReentries
    /\ slot' = [slot EXCEPT ![e] = "Calling"]
    /\ paid' = [paid EXCEPT ![e] = @ + TicketPrice]    \* the external call
    /\ reentries' = [reentries EXCEPT ![e] = @ + 1]
    /\ UNCHANGED global_clock

(* During the Calling window, attacker's `receive` re-enters refund.
 * The buggy slot check sees Live again (because we never advanced past
 * Calling for this entry's nested call). This is the kill step. *)
Tick ==
    /\ global_clock <= FRESHNESS
    /\ global_clock' = global_clock + 1
    /\ UNCHANGED <<slot, paid, reentries>>

ReenterBuggy(e) ==
    /\ e \in Entries
    /\ slot[e] = "Calling"                    \* in-flight call window
    /\ reentries[e] < MaxReentries
    /\ slot' = slot                            \* no advance — bug shape
    /\ paid' = [paid EXCEPT ![e] = @ + TicketPrice]    \* another payout
    /\ reentries' = [reentries EXCEPT ![e] = @ + 1]
    /\ UNCHANGED global_clock

(* Innermost call returns. Slot transitions to Cleared. This is the
 * effect that SHOULD have happened before the external call. *)
PostClearBuggy(e) ==
    /\ e \in Entries
    /\ slot[e] = "Calling"
    /\ reentries[e] > 0
    /\ slot' = [slot EXCEPT ![e] = "Cleared"]
    /\ paid' = paid
    /\ reentries' = [reentries EXCEPT ![e] = 0]    \* unwind cascade
    /\ UNCHANGED global_clock

(* ---------------------------------------------------------------------------
   CORRECT refund flow — CEI: clear slot BEFORE external call.

   Single atomic action because the slot is cleared in the same step
   that performs the call (modeled atomically). Even if a re-entry
   could happen inside the call, it'd see slot = Cleared and the guard
   would reject it (Live check fails).

   We define this for refactor-review side-by-side. The Next we *check*
   uses the buggy actions so TLC's counterexample IS the bug shape.
   --------------------------------------------------------------------------- *)
RefundCorrect(e) ==
    /\ e \in Entries
    /\ slot[e] = "Live"
    /\ slot' = [slot EXCEPT ![e] = "Cleared"]     \* clear FIRST
    /\ paid' = [paid EXCEPT ![e] = @ + TicketPrice] \* then external call
    /\ reentries' = reentries
    /\ UNCHANGED global_clock

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)
Next ==
    \/ (\E e \in Entries :
        \/ PreCheckBuggy(e)
        \/ ReenterBuggy(e)
        \/ PostClearBuggy(e))
    \/ Tick

Fairness ==
    \A e \in Entries :
        WF_vars(PreCheckBuggy(e) \/ ReenterBuggy(e) \/ PostClearBuggy(e))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy refund violates.
   =========================================================================== *)

(* Each entry is paid out AT MOST its TicketPrice — the protocol's
 * promise that a refund returns the entrance fee, not multiples of it.
 * The buggy interleaving PreCheckBuggy(e); ReenterBuggy(e); ... drives
 * paid[e] = k * TicketPrice for k >= 2, contradicting the upper bound.
 * That counterexample IS the reentrancy drain. *)
ClaimedAtMostOnce ==
    \A e \in Entries : paid[e] <= TicketPrice

(* Stronger temporal form: paid only ever grows up to its bound, never
 * "overshoots" via reentry. Equivalent to ClaimedAtMostOnce as an
 * invariant; named for clarity. *)
NoDrain == \A e \in Entries : paid[e] <= TicketPrice

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Cumulative payouts grow monotonically — no negative payouts. *)
MonotonicPaid ==
    [][\A e \in Entries : paid[e] <= paid'[e]]_paid

(* Slot lifecycle progresses forward only:
 *   Live -> Calling -> Cleared
 * never backward. Sanity check on the state machine. *)
SlotProgresses ==
    [][\A e \in Entries :
         /\ (slot[e] = "Cleared") => (slot'[e] = "Cleared")
         /\ (slot[e] = "Calling") => (slot'[e] \in {"Calling", "Cleared"})]_slot

(* Eventually every entry's slot is Cleared (refund terminates under
 * fairness). True for both buggy and correct specs — only the
 * invariant ClaimedAtMostOnce distinguishes them. *)
EventuallyCleared ==
    \A e \in Entries : <>(slot[e] = "Cleared")

StaleDataRejected ==
    \A p \in Entries : paid[p] > 0 => global_clock <= FRESHNESS


=============================================================================
