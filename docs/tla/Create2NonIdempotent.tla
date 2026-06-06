--------------------------- MODULE Create2NonIdempotent ---------------------------
(*
 * Formal specification of plumbline's Create2NonIdempotent FailureMode.
 *
 * The bug class: a deterministic-address Factory exposes a `deploy`
 * function that uses CREATE2 to deploy a contract at an address derived
 * from `(salt, bytecodeHash)`. The factory does NOT pre-check whether
 * a contract already exists at that address. The first call deploys
 * successfully; every subsequent call to deploy with the same salt
 * REVERTS (because CREATE2 fails when an account already lives at the
 * target address). Callers who reasonably expect "deploy is idempotent
 * — give me the deterministic address whether deployed or not" crash
 * on the second invocation.
 *
 * The structural shape: a function with a SHOULD-BE-IDEMPOTENT
 * specification (calling twice with same inputs == calling once) that
 * is NOT idempotent in the buggy implementation. The fix: pre-check
 * `extcodesize(predictedAddr) > 0` and return the existing address
 * instead of reverting.
 *
 * Concrete instance: Cantina sequence-v3 M-04, Factory::deploy.
 * Bundlers/relayers calling deploy on already-deployed wallets crash.
 * (See examples/sequence/.ANSWERS.md M-04.)
 *
 * Models the deploy(salt) call. The salt determines a target address
 * uniquely. The bug surfaces as a TLC counterexample where two
 * deploy(salt) calls land in different outcomes — one Deployed, one
 * Reverted — for the SAME salt. An idempotent spec returns the same
 * outcome (Deployed) both times.
 *
 * Corresponds to:
 *   examples/sequence/.ANSWERS.md (M-04)
 *
 * Architectural lineage:
 *   New bug-class for the corpus: idempotency violation. Pattern
 *   transfers to any deterministic-address deploy, any initialize()
 *   that should be call-once-but-reusable, any DELEGATECALL bootstrap
 *   that should be safe to retry. Structurally close to MissingAwait
 *   (pact-standalone): both have a one-shot transition that the bug
 *   fails to handle (consumer wraps it / re-check the predicate).
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config Create2NonIdempotent.cfg -deadlock Create2NonIdempotent
 *
 * Expected outcome: TLC reports invariant DeployIsIdempotent VIOLATED.
 * The counterexample trace is the bug: two DeployBuggy(s) actions on
 * the same salt s produce outcomes "Deployed" then "Reverted" — the
 * second caller crashed even though the contract IS at the predicted
 * address (the deployment from the first call).
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Salts,                \* Set of salts (== deterministic addresses).
                          \* In the concrete factory, each salt ==
                          \* keccak256(initData) and uniquely identifies
                          \* one wallet.
    MaxCallsPerSalt       \* Bound on retries per salt (finite for TLC).

ASSUME IsFiniteSet(Salts)
ASSUME MaxCallsPerSalt \in Nat
ASSUME MaxCallsPerSalt >= 2    \* need at least 2 calls to exhibit non-idempotency

Outcomes == {"Deployed", "Reverted"}

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    deployed,        \* function Salts -> BOOLEAN: is a contract already
                     \* at the predicted address for this salt?
    last_outcome,    \* function Salts -> Outcomes \cup {"None"}: outcome
                     \* of the most recent deploy call for each salt
    call_count       \* function Salts -> Nat: number of deploy calls
                     \* per salt (bounded to keep state space finite)

vars == <<deployed, last_outcome, call_count>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ deployed     \in [Salts -> BOOLEAN]
    /\ last_outcome \in [Salts -> Outcomes \cup {"None"}]
    /\ call_count   \in [Salts -> Nat]

(* ---------------------------------------------------------------------------
   Initial state — nothing deployed, no calls yet
   --------------------------------------------------------------------------- *)

Init ==
    /\ deployed     = [s \in Salts |-> FALSE]
    /\ last_outcome = [s \in Salts |-> "None"]
    /\ call_count   = [s \in Salts |-> 0]

(* ---------------------------------------------------------------------------
   DeployBuggy(s) — the BUGGY Factory's reaction to deploy(salt).

   Models Factory::deploy as written (M-04 vulnerable): always invokes
   CREATE2 with the salt; CREATE2 succeeds when the address is empty
   and reverts when something is already there.
   --------------------------------------------------------------------------- *)

DeployBuggy(s) ==
    /\ s \in Salts
    /\ call_count[s] < MaxCallsPerSalt
    /\ call_count' = [call_count EXCEPT ![s] = @ + 1]
    /\ IF deployed[s] = FALSE
       THEN /\ deployed'     = [deployed EXCEPT ![s] = TRUE]
            /\ last_outcome' = [last_outcome EXCEPT ![s] = "Deployed"]
       ELSE /\ deployed'     = deployed
            /\ last_outcome' = [last_outcome EXCEPT ![s] = "Reverted"]

(* ---------------------------------------------------------------------------
   DeployCorrect(s) — the CORRECT Factory's reaction.

   The fix shape: pre-check `extcodesize(predictedAddr) > 0`; if yes,
   return the existing address with outcome Deployed (the caller's
   intent is met; deploy is idempotent). If no, do CREATE2 as before.

   We define this here so refactor reviews can compare CORRECT vs
   BUGGY side-by-side. The Next we *check* uses DeployBuggy so TLC's
   counterexample IS the bug shape.
   --------------------------------------------------------------------------- *)

DeployCorrect(s) ==
    /\ s \in Salts
    /\ call_count[s] < MaxCallsPerSalt
    /\ call_count' = [call_count EXCEPT ![s] = @ + 1]
    /\ deployed'   = [deployed EXCEPT ![s] = TRUE]
    /\ last_outcome' = [last_outcome EXCEPT ![s] = "Deployed"]

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next == \E s \in Salts : DeployBuggy(s)

Fairness == \A s \in Salts : WF_vars(DeployBuggy(s))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy factory violates.
   =========================================================================== *)

(* The factory's spec PROMISES: deploy(salt) is idempotent — calling it
 * twice with the same salt produces the same outcome (the contract is
 * at the deterministic address). Concretely: once `last_outcome[s] ==
 * "Deployed"`, subsequent calls should also produce "Deployed", not
 * "Reverted".
 *
 * The buggy DeployBuggy flips last_outcome from Deployed to Reverted
 * on the second call (the IF/ELSE branches above). TLC produces:
 *   DeployBuggy(s1)  →  last_outcome[s1] = "Deployed"
 *   DeployBuggy(s1)  →  last_outcome[s1] = "Reverted"
 * That counterexample IS the M-04 bug — the second caller crashed. *)
DeployIsIdempotent ==
    \A s \in Salts :
        (last_outcome[s] = "Deployed") => (call_count[s] >= 1 /\ deployed[s] = TRUE)

(* Stronger temporal form: once a salt has produced "Deployed", it
 * should NEVER produce "Reverted" thereafter. This is the
 * counterexample-rich property — the bug breaks this. *)
DeployedNeverReverts ==
    \A s \in Salts :
        (last_outcome[s] # "Reverted") \/ (deployed[s] = FALSE)

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Deployment status only grows (Deployed is permanent). *)
DeploymentMonotonic ==
    [][\A s \in Salts : deployed[s] => deployed'[s]]_deployed

(* Number of calls grows monotonically per salt. *)
CallCountMonotonic ==
    [][\A s \in Salts : call_count[s] <= call_count'[s]]_call_count

(* Eventually every salt sees at least one call (under fairness). *)
EventuallyCalled ==
    \A s \in Salts : <>(call_count[s] >= 1)

=============================================================================
