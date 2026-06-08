\* MUTATION: action_subdivide(SignatureReplay)
\* parent: SignatureReplay
\* trace_hash: 6462e20d25a4

--------------------------- MODULE SignatureReplay_Subdiv ---------------------------
(*
 * Formal specification of plumbline's SignatureReplay FailureMode.
 *
 * The bug class: a withdrawal protocol that authorizes payouts via off-chain
 * signatures but does NOT bind each signature to a single use (no nonce,
 * no expiry, no per-signature consumed flag). The same signature can be
 * submitted repeatedly, draining funds far beyond what the signer
 * authorized.
 *
 * Concrete instance: Cyfrin boss-bridge H-3, L1BossBridge::withdrawTokensToL1.
 * The signed message is abi.encode(token, 0, transferFrom(vault, to, amount));
 * NO nonce, NO expiry. The same (v,r,s) submitted N times pays N*amount.
 * (See examples/boss-bridge/.ANSWERS.md H-3.)
 *
 * Models the lifecycle of a signature: created → submitted (1+ times) → paid.
 * The bug surfaces as a TLC counterexample where a single signature drives
 * the cumulative paid amount strictly above its authorized single-shot value.
 *
 * Corresponds to:
 *   examples/boss-bridge/L1BossBridge.sol (withdrawTokensToL1)
 *   examples/boss-bridge/.ANSWERS.md (H-3)
 *
 * Architectural lineage:
 *   Patterned after pact-standalone/docs/tla/MutableDefaultArg.tla
 *   per ADR-004 (TLA+ as Semantic Layer for Solidity), itself adapted from
 *   pact-standalone/docs/adr/ADR-003-tla-as-semantic-layer.md.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config SignatureReplay.cfg -deadlock SignatureReplay
 *
 * Expected outcome: TLC reports invariant NoOverpayment VIOLATED. The
 * counterexample trace is the bug: one signature submitted N times pays
 * N * AuthAmount > AuthAmount, contradicting the protocol's promise that
 * a single signature authorizes a single payout.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Sigs,                  \* Set of off-chain signatures, each binding a
                           \* (signer, recipient, amount) triple. In the
                           \* concrete bridge, sig = ECDSA over
                           \* keccak256(abi.encode(token,0,calldata))
    SigAuth,               \* Scalar Nat: the authorized payout per sig.
                           \* Modeled uniformly so the TLC config grammar
                           \* doesn't need function literals (cfg has a
                           \* more restrictive grammar than .tla).
    MaxSubmissions         \* Bound on how many times any one sig may be
                           \* submitted to the bridge. Finite for TLC.

ASSUME IsFiniteSet(Sigs)
ASSUME SigAuth \in Nat
ASSUME MaxSubmissions \in Nat

\* Derived: each sig authorizes SigAuth (uniformly, for the model).
\* In a richer spec, AuthAmount could vary per-sig; keeping it uniform
\* keeps the cfg simple and TLC's grammar happy.
AuthAmount(s) == SigAuth

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    submissions,    \* function Sigs -> Nat: how many times each sig has been
                    \* submitted to the bridge so far
    paid_total,      \* function Sigs -> Nat: cumulative amount paid out per sig
    inflight_state      \* function Sigs -> {"Fresh","InFlight","Consumed"}

vars == <<submissions, paid_total, inflight_state>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ submissions \in [Sigs -> Nat]
    /\ paid_total  \in [Sigs -> Nat]
    /\ inflight_state \in [Sigs -> {"Fresh", "InFlight", "Consumed"}]

(* ---------------------------------------------------------------------------
   Initial state — nothing submitted, nothing paid
   --------------------------------------------------------------------------- *)
Init ==
    /\ submissions = [s \in Sigs |-> 0]
    /\ paid_total  = [s \in Sigs |-> 0]
    /\ inflight_state   = [s \in Sigs |-> "Fresh"]

(* ---------------------------------------------------------------------------
   SubmitBuggy(s) — the BUGGY bridge's action.

   Models L1BossBridge::withdrawTokensToL1 as written (H-3 vulnerable):
   accepts the signature, performs the transfer for AuthAmount[s] each time
   it's submitted. No consumed-set check.
   --------------------------------------------------------------------------- *)
SubmitBuggy_pre(s) ==
    /\ s \in Sigs
    /\ inflight_state[s] = "Fresh"
    /\ submissions[s] < MaxSubmissions
    /\ inflight_state' = [inflight_state EXCEPT ![s] = "InFlight"]
    /\ paid_total'  = [paid_total  EXCEPT ![s] = @ + AuthAmount(s)]
    /\ UNCHANGED submissions

Reenter_SubmitBuggy(s) ==
    /\ s \in Sigs
    /\ inflight_state[s] = "InFlight"
    /\ submissions[s] < MaxSubmissions
    /\ paid_total'  = [paid_total  EXCEPT ![s] = @ + AuthAmount(s)]
    /\ UNCHANGED <<submissions, inflight_state>>

SubmitBuggy_post(s) ==
    /\ s \in Sigs
    /\ inflight_state[s] = "InFlight"
    /\ inflight_state' = [inflight_state EXCEPT ![s] = "Consumed"]
    /\ submissions' = [submissions EXCEPT ![s] = @ + 1]
    /\ UNCHANGED paid_total

SubmitCorrect(s) ==
    /\ s \in Sigs
    /\ submissions[s] = 0                  \* one-shot gate (the missing nonce)
    /\ submissions' = [submissions EXCEPT ![s] = 1]
    /\ paid_total'  = [paid_total  EXCEPT ![s] = AuthAmount(s)]

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next ==
    \E s \in Sigs :
        \/ SubmitBuggy_pre(s)
        \/ Reenter_SubmitBuggy(s)
        \/ SubmitBuggy_post(s)

Fairness ==
    \A s \in Sigs :
        WF_vars(SubmitBuggy_pre(s) \/ Reenter_SubmitBuggy(s) \/ SubmitBuggy_post(s))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy bridge violates.
   =========================================================================== *)

(* Each signature pays out at most its authorized amount, in total.
 * This is the property the protocol PROMISES: one signature = one payment
 * = AuthAmount[s]. The buggy SubmitBuggy action does not respect this
 * upper bound, so TLC will produce a counterexample: a sequence of
 * (SubmitBuggy(s), SubmitBuggy(s), ...) submissions for some single s,
 * driving paid_total[s] = k * AuthAmount[s] > AuthAmount[s]. That
 * counterexample IS the bug. *)
NoOverpayment ==
    \A s \in Sigs : paid_total[s] <= AuthAmount(s)

(* The lighter property — the same sig is never paid twice — is implied
 * by NoOverpayment for any AuthAmount[s] > 0; we name it explicitly as
 * a sanity check for the spec author. *)
PaidAtMostOnce ==
    \A s \in Sigs : submissions[s] <= 1

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Cumulative payouts grow monotonically — no refunds-out-of-thin-air *)
MonotonicPayouts ==
    [][\A s \in Sigs : paid_total[s] <= paid_total'[s]]_paid_total

(* If a signature is ever submitted, it's eventually paid (no payout
 * gets stuck in pending) *)
SubmittedEventuallyPaid ==
    \A s \in Sigs :
        (submissions[s] > 0) ~> (paid_total[s] > 0)

=============================================================================
