\* MUTATION: swap_bool(FALSE->TRUE)
\* original hash: 1c8c7d3657e174d3
\* new hash: 4f53cda18c2baa0c

--------------------------- MODULE PartialSignatureReplay ---------------------------
(*
 * Formal specification of plumbline's PartialSignatureReplay FailureMode.
 *
 * The bug class: a wallet/protocol authorizes a BATCH of N calls via a
 * session/aggregate signature. Each individual call within the batch has
 * its own per-call signature. The signature-validation function checks
 * each per-call signature INDEPENDENTLY without binding the per-call
 * signature to the batch identity (no batch nonce, batch hash, or call
 * index in the signed payload). Therefore an attacker can extract one
 * per-call signature from the batch and submit it ALONE (or recombine
 * call signatures across batches) and pass validation.
 *
 * Structural shape: "per-element guard without group binding." Distinct
 * from SignatureReplay (no guard at all) and ReentrancyDrain (guard
 * misplaced relative to external call). Here the guard EXISTS at the
 * right place per-element, but the GROUP CONTEXT is not bound — so the
 * guard is bypassable by re-grouping.
 *
 * Concrete instance: Cantina sequence-v3 H-02, SessionSig validating
 * each call's signature independently without binding to batch
 * identity/nonce/index.
 * (See examples/sequence/.ANSWERS.md H-02.)
 *
 * Models a session batch authorizing a set of calls. The buggy
 * validator accepts ANY subset of the batch's per-call signatures
 * submitted in any grouping. The fix binds each per-call signature
 * to the parent batch (e.g., include batch_id in the per-call signed
 * payload, or check that all batch members are present).
 *
 * Corresponds to:
 *   examples/sequence/.ANSWERS.md (H-02)
 *
 * Architectural lineage:
 *   Distinct from SignatureReplay (one-shot promise WITHOUT a guard).
 *   Distinct from ERC4337StaticSigDoS (caller-bound auth misreads
 *   msg.sender). This is the FIRST corpus shape that models a BATCH
 *   structure where each element has a per-element guard.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config PartialSignatureReplay.cfg -deadlock PartialSignatureReplay
 *
 * Expected outcome: TLC reports invariant BatchIntegrity VIOLATED. The
 * counterexample: a per-call signature from batch b1 is submitted as a
 * STANDALONE call (group of size 1, not the original batch of N), and
 * the buggy validator accepts it — executing the call outside its
 * authorized batch context.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    NumCalls,        \* Number of calls / batches (Calls = Batches = 1..NumCalls
                     \* for the model; each call is in its same-numbered
                     \* batch). Modeled with scalars to keep .cfg grammar
                     \* simple (TLC's .cfg can't take function literals).
    MaxSubmissions   \* Bound for TLC

ASSUME NumCalls       \in Nat
ASSUME MaxSubmissions \in Nat
ASSUME NumCalls > 0

Calls   == 1..NumCalls
Batches == 1..NumCalls

(* Each call c belongs to its same-numbered batch. The bug fires when
 * a call is submitted under a DIFFERENT batch context (BatchOf[c] # b). *)
BatchOf(c) == c

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    executed,           \* function Calls -> BOOLEAN: has this call run?
    submitted_in_batch, \* function Calls -> Nat:
                        \* the batch context this call was submitted under
                        \* (0 = not yet submitted).
    submissions_total   \* Nat: total submissions (TLC bound)

vars == <<executed, submitted_in_batch, submissions_total>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ executed           \in [Calls -> BOOLEAN]
    /\ submitted_in_batch \in [Calls -> Nat]
    /\ submissions_total  \in Nat

(* ---------------------------------------------------------------------------
   Initial state — nothing executed, no submissions
   --------------------------------------------------------------------------- *)

Init ==
    /\ executed           = [c \in Calls |-> TRUE]
    /\ submitted_in_batch = [c \in Calls |-> 0]
    /\ submissions_total  = 0

(* ---------------------------------------------------------------------------
   SubmitBuggy(c, b) — the BUGGY validator's reaction.

   Models the SessionSig validator from H-02: accepts call c's per-call
   signature as long as c's signature is valid IN ISOLATION. The
   "submitted-under-batch" context b can be ANY batch (including a
   single-call batch crafted by the attacker), not necessarily BatchOf[c].

   The bug surfaces when SubmitBuggy(c, b) with b # BatchOf[c] succeeds —
   the validator never checks that the submission's batch context matches
   the call's authorized batch context.
   --------------------------------------------------------------------------- *)

SubmitBuggy(c, b) ==
    /\ c \in Calls
    /\ b \in Batches
    /\ executed[c] = FALSE                          \* per-call guard exists
    /\ submissions_total < MaxSubmissions
    /\ executed'           = [executed EXCEPT ![c] = TRUE]
    /\ submitted_in_batch' = [submitted_in_batch EXCEPT ![c] = b]
    /\ submissions_total'  = submissions_total + 1

(* ---------------------------------------------------------------------------
   SubmitCorrect(c, b) — the CORRECT validator's reaction.

   The fix: require the submitted-under-batch context b to equal BatchOf[c].
   This is the "bind batch identity to per-call sig" fix shape — include
   batch_id (or hash) in the per-call signed payload.
   --------------------------------------------------------------------------- *)

SubmitCorrect(c, b) ==
    /\ c \in Calls
    /\ b \in Batches
    /\ executed[c] = FALSE
    /\ b = BatchOf(c)                               \* binding check
    /\ submissions_total < MaxSubmissions
    /\ executed'           = [executed EXCEPT ![c] = TRUE]
    /\ submitted_in_batch' = [submitted_in_batch EXCEPT ![c] = b]
    /\ submissions_total'  = submissions_total + 1

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next == \E c \in Calls : \E b \in Batches : SubmitBuggy(c, b)

Fairness == \A c \in Calls : WF_vars(\E b \in Batches : SubmitBuggy(c, b))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy validator violates.
   ===========================================================================

 * The validator PROMISES: a per-call signature is consumed AS PART OF
 * its authorized parent batch. Concretely: if a call c is executed,
 * the batch it was submitted under must equal the batch it was
 * authorized in. The buggy SubmitBuggy permits arbitrary b, so
 * submitted_in_batch[c] # BatchOf[c] is reachable.
 *
 * That counterexample IS the H-02 bug — the per-call sig from batch
 * b1 was submitted in a different batch context (or alone), bypassing
 * the user's batch authorization.
 *)
BatchIntegrity ==
    \A c \in Calls :
        executed[c] => (submitted_in_batch[c] = BatchOf(c))

(* Sanity invariants *)
NoExecutionWithoutSubmission ==
    \A c \in Calls :
        executed[c] => (submitted_in_batch[c] # 0)

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Execution is monotonic — never unexecutes *)
ExecutionMonotonic ==
    [][\A c \in Calls : executed[c] => executed'[c]]_executed

=============================================================================
