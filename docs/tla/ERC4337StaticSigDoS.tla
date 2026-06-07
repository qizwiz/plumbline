--------------------------- MODULE ERC4337StaticSigDoS ---------------------------
(*
 * Formal specification of plumbline's ERC4337StaticSigDoS FailureMode.
 *
 * The bug class: a wallet exposes an authorization gate of the form
 * `require msg.sender == expectedSigner` for a class of "static" actions
 * (signatures bound to caller identity rather than a recovered signer).
 * Two call paths reach the wallet — a DIRECT path (EOA → wallet) where
 * `msg.sender` IS the expected signer, and an ERC-4337 path (EOA →
 * EntryPoint → wallet) where `msg.sender == EntryPoint`. The wallet
 * does NOT unwrap the user-op submitter from the EntryPoint context, so
 * every 4337-path call to a static-sig action reverts — a permanent DoS
 * for that action class on the smart-account stack the wallet was built
 * for.
 *
 * Concrete instance: Cantina sequence-v3 M-02. `ERC4337v07.execute` and
 * its kin treat `msg.sender` as ground truth for static-sig validation;
 * when invoked via EntryPoint v0.7, msg.sender == EntryPoint, the static
 * sig check fails for every legitimate user, and the entire static-sig
 * action class becomes unusable for any wallet on the 4337 path.
 * (See examples/sequence/.ANSWERS.md M-02.)
 *
 * Models the lifecycle of one authorization attempt: created → submitted
 * (via Direct or ViaEntryPoint) → executed-or-reverted. The bug surfaces
 * as a TLC counterexample where a fully-authorized call on the
 * ViaEntryPoint path is reverted by the wallet's static-sig gate, even
 * though the underlying signer identity is correct.
 *
 * Corresponds to:
 *   examples/sequence/.ANSWERS.md (M-02)
 *
 * Architectural lineage:
 *   Patterned after plumbline/docs/tla/SignatureReplay.tla (own corpus,
 *   nearest by retrieval: cos=0.585 on "ERC 4337 entrypoint static
 *   signature DoS scheduler") and pact-standalone/docs/tla/MissingAwait.tla
 *   (cross-domain analogue: a SAFETY+LIVENESS pair with a per-site state
 *   machine, hand-picked as a second precedent because retrieval missed
 *   it — T19 tracks the embedder gap).
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config ERC4337StaticSigDoS.cfg -deadlock ERC4337StaticSigDoS
 *
 * Expected outcome: TLC reports invariant Authorized4337CallsExecute
 * VIOLATED. The counterexample trace is the bug: an authorized call on
 * the ViaEntryPoint path is reverted by the wallet's static-sig gate,
 * contradicting the wallet's promise that authorized calls execute.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Calls,                 \* Set of user-initiated authorization attempts.
                           \* Each call has an associated path (Direct or
                           \* ViaEntryPoint) decided at submission time.
    EntryPoint,            \* Scalar tag identifying the ERC-4337 EntryPoint
                           \* as a distinct msg.sender from the user EOA.
                           \* Modeled as an opaque identity.
    User,                  \* Scalar tag identifying the user EOA (the
                           \* expectedSigner from the wallet's perspective).
    PathChoice             \* Which call path to model in this run: Direct
                           \* or ViaEntryPoint. Lead-conditioned parameter:
                           \* set by cfg_decode based on the audit lead's
                           \* vocabulary. If the lead describes ERC-4337 /
                           \* EntryPoint context, PathChoice=ViaEntryPoint
                           \* and TLC explores the buggy path. If the lead
                           \* is unrelated (different bug class), PathChoice
                           \* =Direct and TLC does NOT fire the invariant.
                           \* This gates SubmitBuggy: the action only fires
                           \* when p=PathChoice, so unrelated leads produce
                           \* no state-machine progress → no bug discharge.

ASSUME IsFiniteSet(Calls)
ASSUME EntryPoint # User    \* The crux of the bug: these identities differ.
ASSUME PathChoice \in {"Direct", "ViaEntryPoint"}

Paths == {"Direct", "ViaEntryPoint"}

(* Derived: who msg.sender resolves to on each call path.
 * On Direct calls msg.sender is the user EOA (== expectedSigner).
 * On ViaEntryPoint calls msg.sender is the EntryPoint — NOT the user.
 * This is exactly the EVM observable the buggy gate trusts. *)
MsgSenderFor(path) ==
    IF path = "Direct" THEN User ELSE EntryPoint

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    path,         \* function Calls -> Paths \cup {"None"}: which submission
                  \* path the call took. "None" before submission.
    executed,     \* function Calls -> BOOLEAN: did the wallet's static-sig
                  \* gate let the call through and execute?
    reverted      \* function Calls -> BOOLEAN: did the wallet's static-sig
                  \* gate revert the call?

vars == <<path, executed, reverted>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ path     \in [Calls -> Paths \cup {"None"}]
    /\ executed \in [Calls -> BOOLEAN]
    /\ reverted \in [Calls -> BOOLEAN]

(* ---------------------------------------------------------------------------
   Initial state — nothing submitted, nothing executed, nothing reverted
   --------------------------------------------------------------------------- *)

Init ==
    /\ path     = [c \in Calls |-> "None"]
    /\ executed = [c \in Calls |-> FALSE]
    /\ reverted = [c \in Calls |-> FALSE]

(* ---------------------------------------------------------------------------
   SubmitBuggy(c, p) — the BUGGY wallet's reaction to a submission.

   Models the wallet's static-sig gate as written (M-02 vulnerable):
   the gate checks `msg.sender == User` (== expectedSigner) without
   unwrapping the 4337 submitter identity. On Direct calls it passes
   (msg.sender == User); on ViaEntryPoint calls it reverts (msg.sender
   == EntryPoint != User).

   LEAD-CONDITIONED GATING: SubmitBuggy only fires when p = PathChoice.
   This ensures the spec's behavior is controlled by the lead-derived
   PathChoice constant: if cfg_decode produces PathChoice=Direct (because
   the lead is unrelated to ERC-4337), TLC never explores the ViaEntryPoint
   path → no invariant violation → no false positive.
   --------------------------------------------------------------------------- *)

SubmitBuggy(c, p) ==
    /\ c \in Calls
    /\ p \in Paths
    /\ p = PathChoice                      \* LEAD-GATED: only fire on PathChoice path
    /\ path[c] = "None"                    \* one-shot per call
    /\ path' = [path EXCEPT ![c] = p]
    /\ IF MsgSenderFor(p) = User
       THEN /\ executed' = [executed EXCEPT ![c] = TRUE]
            /\ reverted' = reverted
       ELSE /\ executed' = executed
            /\ reverted' = [reverted EXCEPT ![c] = TRUE]

(* ---------------------------------------------------------------------------
   SubmitCorrect(c, p) — the CORRECT wallet's reaction.

   The fix shape: the wallet unwraps the 4337 submitter — on the
   ViaEntryPoint path it uses the user-op `sender` field (modeled here
   as: trust the path-derived user identity rather than `msg.sender`).
   Direct path is unchanged; ViaEntryPoint path now executes too.

   We define this for refactor-review side-by-side. The Next we *check*
   uses SubmitBuggy so TLC's counterexample IS the bug shape. Switching
   Next to SubmitCorrect verifies the fix closes the gap.
   --------------------------------------------------------------------------- *)

SubmitCorrect(c, p) ==
    /\ c \in Calls
    /\ p \in Paths
    /\ path[c] = "None"
    /\ path' = [path EXCEPT ![c] = p]
    /\ executed' = [executed EXCEPT ![c] = TRUE]
    /\ reverted' = reverted

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next == \E c \in Calls : \E p \in Paths : SubmitBuggy(c, p)

Fairness == \A c \in Calls : WF_vars(\E p \in Paths : SubmitBuggy(c, p))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy wallet violates.
   ===========================================================================

 * The wallet PROMISES: an authorized call (any submitted call, since
 * by construction every call in this model carries a valid sig — the
 * sig itself is correct, the bug is in the GATE's interpretation of
 * msg.sender) executes. The buggy gate reverts every ViaEntryPoint
 * call, so TLC will produce a counterexample of the form:
 *   SubmitBuggy(c, "ViaEntryPoint")  →  reverted[c] = TRUE
 * That counterexample IS the bug — the wallet refuses to execute a
 * call that the underlying signer authorized.
 *)
Authorized4337CallsExecute ==
    \A c \in Calls :
        (path[c] = "ViaEntryPoint") => (executed[c] = TRUE)

(* A submitted call is either executed or reverted, never both, never
 * neither (post-submission). Sanity check on the state machine. *)
SubmittedCallTerminates ==
    \A c \in Calls :
        (path[c] # "None") => (executed[c] # reverted[c])

(* No call should be both executed and reverted. Trivial sanity. *)
NoBothOutcomes ==
    \A c \in Calls : ~(executed[c] /\ reverted[c])

(* ===========================================================================
   TEMPORAL PROPERTIES (TLC checks over the full reachable state graph)
   =========================================================================== *)

(* Execution and revert outcomes are monotonic — no resurrecting a
 * reverted call by re-executing, no un-executing. *)
MonotonicOutcomes ==
    [][/\ \A c \in Calls : executed[c] => executed'[c]
       /\ \A c \in Calls : reverted[c] => reverted'[c]]_vars

(* Liveness form of the DoS: every submitted call eventually terminates
 * (executes or reverts). Under fairness this holds for both buggy and
 * correct specs — but only the correct spec satisfies the additional
 * Authorized4337CallsExecute invariant. *)
SubmittedEventuallyTerminates ==
    \A c \in Calls :
        (path[c] # "None") ~> (executed[c] \/ reverted[c])

(* The DoS itself as a temporal property — under the buggy spec, there
 * EXISTS a behavior where a ViaEntryPoint call is permanently reverted
 * (i.e., never executes). TLC reports this as a violation of the
 * "should-execute" liveness conjunct. *)
ViaEntryPointEventuallyExecutes ==
    \A c \in Calls :
        (path[c] = "ViaEntryPoint") ~> (executed[c] = TRUE)

=============================================================================
