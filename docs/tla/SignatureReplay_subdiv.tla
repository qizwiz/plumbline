--------------------------- MODULE SignatureReplay_subdiv ---------------------------
(*
 * Manual action_subdivide experiment on SignatureReplay.tla.
 *
 * The original SubmitBuggy(s) is one atomic action that both increments
 * the submissions counter AND adds AuthAmount to paid_total. We split it
 * into two atomic actions with an intermediate "InFlight" state:
 *
 *   SubmitBuggy_pre(s) — Idle → InFlight, increment submissions counter
 *   SubmitBuggy_post(s) — InFlight → Idle, pay out AuthAmount
 *
 * Then we add a third action — ReentryDuringInFlight(s, t) — that fires
 * while sig s is InFlight and re-submits a DIFFERENT signature t. This
 * is the cross-signature reentry pattern: during s's pending payout,
 * an attacker's receive() submits another signature.
 *
 * Predicted shape: ReentrantSignatureReplay — drains by chaining different
 * signatures during a single external-call window.
 *
 * If TLC discharges this and the embedding shifts AND it covers some of
 * the 146 unmatched Sherlock findings, the action_subdivide design from
 * docs/architecture/SHAPE_GRAPH_MUTATIONS.md is validated.
 *)

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Sigs,
    SigAuth,
    MaxSubmissions

ASSUME IsFiniteSet(Sigs)
ASSUME SigAuth \in Nat
ASSUME MaxSubmissions \in Nat
ASSUME MaxSubmissions >= 2

AuthAmount(s) == SigAuth

\* NEW: per-signature lifecycle state. The intermediate "InFlight"
\* exposes the reentry window.
SigStates == {"Idle", "InFlight"}

VARIABLES
    submissions,    \* function Sigs -> Nat
    paid_total,     \* function Sigs -> Nat
    sig_state       \* function Sigs -> SigStates (NEW — the intermediate)

vars == <<submissions, paid_total, sig_state>>

TypeInvariant ==
    /\ submissions \in [Sigs -> Nat]
    /\ paid_total \in [Sigs -> Nat]
    /\ sig_state \in [Sigs -> SigStates]

Init ==
    /\ submissions = [s \in Sigs |-> 0]
    /\ paid_total  = [s \in Sigs |-> 0]
    /\ sig_state   = [s \in Sigs |-> "Idle"]

(* --- The split: pre = Idle→InFlight + counter, post = InFlight→Idle + payout --- *)

SubmitBuggy_pre(s) ==
    /\ s \in Sigs
    /\ sig_state[s] = "Idle"
    /\ submissions[s] < MaxSubmissions
    /\ submissions' = [submissions EXCEPT ![s] = @ + 1]
    /\ sig_state'   = [sig_state   EXCEPT ![s] = "InFlight"]
    /\ paid_total'  = paid_total              \* paid_total unchanged

SubmitBuggy_post(s) ==
    /\ s \in Sigs
    /\ sig_state[s] = "InFlight"
    /\ paid_total'  = [paid_total EXCEPT ![s] = @ + AuthAmount(s)]
    /\ sig_state'   = [sig_state  EXCEPT ![s] = "Idle"]
    /\ submissions' = submissions             \* submissions unchanged

(* --- The new reentry action: while s is InFlight, attacker submits a different sig t --- *)

ReentryDuringInFlight(s, t) ==
    /\ s \in Sigs
    /\ t \in Sigs
    /\ s /= t
    /\ sig_state[s] = "InFlight"             \* we're mid-payout for s
    /\ sig_state[t] = "Idle"                  \* reentry submits a DIFFERENT signature
    /\ submissions[t] < MaxSubmissions
    /\ submissions' = [submissions EXCEPT ![t] = @ + 1]
    /\ sig_state'   = [sig_state   EXCEPT ![t] = "InFlight"]
    /\ paid_total'  = paid_total

Next ==
    \E s \in Sigs :
        \/ SubmitBuggy_pre(s)
        \/ SubmitBuggy_post(s)
        \/ \E t \in Sigs : ReentryDuringInFlight(s, t)

Fairness ==
    \A s \in Sigs :
        WF_vars(SubmitBuggy_pre(s) \/ SubmitBuggy_post(s))

Spec == Init /\ [][Next]_vars /\ Fairness

(* === THE NEW INVARIANT — captures the reentrant-during-payout bug === *)

(* The strong claim of the original bug class: no signature is paid more than once. *)
NoOverpayment ==
    \A s \in Sigs : paid_total[s] <= AuthAmount(s)

(* NEW INVARIANT specific to the subdivided shape: at most one signature
 * is InFlight at any time. The buggy spec violates this because reentry
 * during s's InFlight window can move t to InFlight too. This invariant
 * would HOLD on the original (non-subdivided) atomic spec because the
 * intermediate state didn't exist. *)
AtMostOneInFlight ==
    Cardinality({s \in Sigs : sig_state[s] = "InFlight"}) <= 1

=============================================================================
