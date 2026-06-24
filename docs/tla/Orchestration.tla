------------------------- MODULE Orchestration -------------------------
(*
 * Formal model of plumbline's MULTI-AGENT ORCHESTRATION fabric — the
 * coordination layer, not a smart-contract bug.
 *
 * N specialist proposer agents (solvency, precision, access) propose
 * findings; a dispatcher routes each to a verifier and resolves it to a
 * terminal verdict. The dispatcher RETRIES a transient verifier failure
 * (TOOL_ERROR: timeout/crash) up to a CAP, then escalates. This matches
 * tools/orchestrator.py exactly:
 *   _verify_with_retry  retries a TOOL_ERROR up to MAX_VERIFY_ATTEMPTS
 *                       (the `Retry` action, capped by MaxAttempts)
 *   the dispatch then escalates the final TOOL_ERROR   (`EscalateAtCap`)
 *
 * THIS MODEL IS LOAD-BEARING — it verifies a real design decision against
 * a real hazard. The retry cap + the escalate-after-cap are what make the
 * dispatch terminate even when a verifier persistently fails:
 *   - Spec (capped + escalate): Liveness, Completion, NoStarvation HOLD,
 *     and retries never exceed the cap (RetriesCapped).
 *   - NoCapSpec (drop the escalate-after-cap fallback — e.g. an uncapped
 *     `while TOOL_ERROR: retry` that never gives up): a persistently-
 *     failing verifier leaves the finding pending forever, so Liveness
 *     FAILS and TLC returns the counterexample.
 *
 * So removing the cap fallback is not safe-by-construction — TLC proves it
 * breaks termination, and the implementation is the version that doesn't.
 *
 * Corresponds to:
 *   tools/orchestrator.py  (_verify_with_retry, MAX_VERIFY_ATTEMPTS, dispatch)
 *   tools/verifier.py      (run_verifier -> TOOL_ERROR on timeout/exception)
 *)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Agents,         \* the specialist proposer agents, e.g. {solvency, precision, access}
    MaxFindings,    \* findings each agent may propose (bound for finite-state checking)
    MaxAttempts     \* the retry cap (= MAX_VERIFY_ATTEMPTS in orchestrator.py)

VARIABLES
    todo,           \* [Agents -> Nat] : findings each agent has yet to propose
    pending,        \* SUBSET Findings : proposed, not yet resolved
    resolved,       \* SUBSET Findings : reached a terminal verdict
    attempts        \* [Findings -> Nat] : transient-failure retries used so far

vars == << todo, pending, resolved, attempts >>

Findings == Agents \X (1 .. MaxFindings)    \* a finding is << agent, id >>

TypeOK ==
    /\ todo \in [Agents -> 0 .. MaxFindings]
    /\ pending \subseteq Findings
    /\ resolved \subseteq Findings
    /\ attempts \in [Findings -> 0 .. MaxAttempts]

\* SAFETY: the gate is the single owner of a verdict.
GateIsSingleOwner == pending \cap resolved = {}

\* SAFETY: the retry cap is respected — no finding is retried more than MaxAttempts times.
RetriesCapped == \A f \in Findings : attempts[f] <= MaxAttempts

Init ==
    /\ todo = [a \in Agents |-> MaxFindings]
    /\ pending = {}
    /\ resolved = {}
    /\ attempts = [f \in Findings |-> 0]

\* A specialist agent proposes its next finding (agents interleave).
Propose(a) ==
    /\ todo[a] > 0
    /\ pending' = pending \cup { << a, (MaxFindings - todo[a] + 1) >> }
    /\ todo' = [todo EXCEPT ![a] = @ - 1]
    /\ UNCHANGED << resolved, attempts >>

\* The verifier SUCCEEDED on this attempt -> resolve (CONFIRMED / CLEARED / ESCALATED).
ResolveOk(f) ==
    /\ f \in pending
    /\ pending' = pending \ {f}
    /\ resolved' = resolved \cup {f}
    /\ UNCHANGED << todo, attempts >>

\* The verifier hit a TRANSIENT failure (TOOL_ERROR) -> retry, bounded by the cap.
Retry(f) ==
    /\ f \in pending
    /\ attempts[f] < MaxAttempts
    /\ attempts' = [attempts EXCEPT ![f] = @ + 1]
    /\ UNCHANGED << todo, pending, resolved >>

\* After MaxAttempts transient failures the dispatcher ESCALATES the final TOOL_ERROR and stops.
\* This is _verify_with_retry returning the last result + the dispatch escalating it. It is the
\* fallback that guarantees termination when a verifier persistently fails.
EscalateAtCap(f) ==
    /\ f \in pending
    /\ attempts[f] = MaxAttempts
    /\ pending' = pending \ {f}
    /\ resolved' = resolved \cup {f}
    /\ UNCHANGED << todo, attempts >>

Next ==
    \/ \E a \in Agents : Propose(a)
    \/ \E f \in pending : ResolveOk(f) \/ Retry(f) \/ EscalateAtCap(f)

\* The dispatcher keeps working: it keeps retrying, and it escalates once the cap is hit.
Fairness ==
    /\ \A a \in Agents : WF_vars(Propose(a))
    /\ \A f \in Findings : WF_vars(Retry(f))
    /\ \A f \in Findings : WF_vars(EscalateAtCap(f))

Spec == Init /\ [][Next]_vars /\ Fairness

\* HAZARD: the SAME loop WITHOUT the escalate-after-cap fallback (an uncapped retry that never
\* gives up). A persistently-failing verifier — one whose ResolveOk is never taken — retries to
\* the cap and then has no terminal step, so the finding stays pending forever and Liveness FAILS.
NextNoCap ==
    \/ \E a \in Agents : Propose(a)
    \/ \E f \in pending : ResolveOk(f) \/ Retry(f)

NoCapSpec ==
    Init /\ [][NextNoCap]_vars
    /\ (\A a \in Agents : WF_vars(Propose(a)))
    /\ (\A f \in Findings : WF_vars(Retry(f)))

----------------------------------------------------------------------------
\* The coordination properties (Jebb's domain: timing + trust across the system)

\* LIVENESS: every finding the agents propose is eventually resolved.
Liveness == \A f \in Findings : (f \in pending) ~> (f \in resolved)

\* COMPLETION: the run always finishes — eventually nothing is left to do.
Completion == <>[] (pending = {} /\ (\A a \in Agents : todo[a] = 0))

\* NO STARVATION: no agent's findings are perpetually skipped by the dispatcher.
NoStarvation == \A a \in Agents :
    (\E f \in pending : f[1] = a) ~> (\E f \in resolved : f[1] = a)

=============================================================================
