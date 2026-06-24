------------------------- MODULE Orchestration -------------------------
(*
 * Formal model of plumbline's MULTI-AGENT ORCHESTRATION fabric — the
 * coordination layer itself, not a smart-contract bug.
 *
 * plumbline runs N specialist proposer agents (solvency, precision,
 * access) in PARALLEL; each proposes findings. A deterministic dispatcher
 * then routes each finding to a verifier and resolves it to a terminal
 * verdict (CONFIRMED / CLEARED / ESCALATED). This module abstracts that
 * loop and asks the questions an autonomous-systems engineer cares about
 * ("latency -> desynchronization -> mission failure"):
 *
 *   - Liveness     : is every proposed finding EVENTUALLY resolved?
 *   - Completion   : does the audit run always terminate (no infinite stall)?
 *   - NoStarvation : is any specialist agent's work perpetually skipped?
 *
 * These hold UNDER the fairness assumptions in `Spec` (weak fairness on
 * each agent's Propose and on the dispatcher's Verify). The assumption is
 * load-bearing, not vacuous: drop the dispatcher's weak fairness
 * (`UnfairSpec`, checked by Orchestration_unfair.cfg) and TLC hands back a
 * starvation counterexample where a proposed finding is never resolved.
 *
 * Corresponds to:
 *   tools/orchestrator.py  (_propose_multi -> route -> dispatch)
 *   tools/verifier.py      (the soundness gate that resolves a finding)
 *)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Agents,         \* the specialist proposer agents, e.g. {solvency, precision, access}
    MaxFindings     \* findings each agent may propose (bound for finite-state checking)

VARIABLES
    todo,           \* [Agents -> Nat] : findings each agent has yet to propose
    pending,        \* SUBSET Findings : proposed, not yet resolved by the gate
    resolved        \* SUBSET Findings : reached a terminal verdict

vars == << todo, pending, resolved >>

Findings == Agents \X (1 .. MaxFindings)    \* a finding is << agent, id >>

TypeOK ==
    /\ todo \in [Agents -> 0 .. MaxFindings]
    /\ pending \subseteq Findings
    /\ resolved \subseteq Findings

\* SAFETY: the gate is the single owner of a verdict — a finding is never
\* simultaneously awaiting verification and already resolved.
GateIsSingleOwner == pending \cap resolved = {}

Init ==
    /\ todo = [a \in Agents |-> MaxFindings]
    /\ pending = {}
    /\ resolved = {}

\* A specialist agent proposes its next finding. Agents run concurrently:
\* any enabled agent may take the next step (interleaving).
Propose(a) ==
    /\ todo[a] > 0
    /\ pending' = pending \cup { << a, (MaxFindings - todo[a] + 1) >> }
    /\ todo' = [todo EXCEPT ![a] = @ - 1]
    /\ UNCHANGED resolved

\* The deterministic dispatcher routes ONE pending finding to a verifier and
\* resolves it. CONFIRMED / CLEARED / ESCALATED are all "resolved" here — we
\* model coordination/progress, not which verdict.
Verify(f) ==
    /\ f \in pending
    /\ pending' = pending \ {f}
    /\ resolved' = resolved \cup {f}
    /\ UNCHANGED todo

Next ==
    \/ \E a \in Agents : Propose(a)
    \/ \E f \in pending : Verify(f)

\* Weak fairness: every agent keeps proposing until done, and the dispatcher
\* keeps resolving anything pending.
Fairness ==
    /\ \A a \in Agents : WF_vars(Propose(a))
    /\ \A f \in Findings : WF_vars(Verify(f))

Spec == Init /\ [][Next]_vars /\ Fairness

\* Same system WITHOUT the dispatcher's weak fairness — used to demonstrate the
\* assumption has teeth (TLC finds a run where the dispatcher starves a finding).
UnfairSpec == Init /\ [][Next]_vars /\ (\A a \in Agents : WF_vars(Propose(a)))

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
