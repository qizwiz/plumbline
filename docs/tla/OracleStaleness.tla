--------------------------- MODULE OracleStaleness ---------------------------
(*
 * Formal specification of plumbline's OracleStaleness FailureMode.
 *
 * The bug class: a financial action (payment, valuation, liquidation,
 * NAV calculation, etc.) consumes an oracle price or external data value
 * WITHOUT checking whether the data is still fresh.  A monotonic
 * global clock advances past the freshness window (FRESHNESS steps);
 * the buggy action then proceeds using the stale data, producing an
 * incorrect settlement.
 *
 * Structural shape: "stale-data-accepted."  There is a FRESHNESS bound
 * (heartbeat timeout, max age, cooldown length, epoch length, etc.).
 * A Tick action advances the oracle age.  The buggy PayBuggy action
 * performs a payment/settlement without the guard `oracle_age <= FRESHNESS`.
 * The correct PayCorrect action includes that guard.
 *
 * TLC counterexample: Init → Tick(1) → Tick(2) → PayBuggy(a1)
 *   oracle_age = 2 > FRESHNESS = 1 when payment fires.
 *   paid_at[a1] = 2 violates StaleDataRejected.
 *
 * Distinct from:
 *  - SignatureReplay (no nonce) — here the issue is timing, not identity
 *  - ReentrancyDrain (CEI order) — not a reentrancy issue; no callback
 *  - Uint64FeeOverflow (accumulator truncation) — not about overflow
 *
 * Covers Sherlock bug classes:
 *  - NAV staleness during cooldown (NAV not recalculated mid-cooldown)
 *  - Oracle versions expired but still accepted as valid
 *  - Stale price feed used for collateral/liquidation decisions
 *  - Stuck emissions for nullified (expired) epochs
 *  - Missing heartbeat / freshness check on Chainlink latestAnswer()
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config OracleStaleness.cfg -deadlock OracleStaleness
 *
 * Expected outcome: TLC reports invariant StaleDataRejected VIOLATED.
 * Counterexample trace: Tick; Tick; PayBuggy(a1) — payment occurs at
 * oracle_age = 2, which exceeds FRESHNESS = 1.  paid_at[a1] = 2.
 * The fix: add oracle_age <= FRESHNESS guard to PayBuggy.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Agents,          \* finite set of accounts that can trigger a payment
    MaxAge,          \* Nat: max oracle age to model (bounds state space for TLC)
    FRESHNESS        \* Nat: max clock steps before oracle data is stale.
                     \* In production: Chainlink heartbeat (3600 s), NAV
                     \* update interval, epoch length, cooldown duration, etc.

ASSUME IsFiniteSet(Agents)
ASSUME FRESHNESS \in Nat
ASSUME MaxAge    \in Nat
ASSUME MaxAge > FRESHNESS   \* must allow age to exceed FRESHNESS for bug to fire

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    oracle_age,      \* Nat: steps since last oracle update (ages via Tick)
    paid,            \* function Agents -> BOOLEAN: whether agent has been paid
    paid_at          \* function Agents -> Nat: oracle_age recorded AT payment time

vars == <<oracle_age, paid, paid_at>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ oracle_age \in 0..MaxAge
    /\ paid       \in [Agents -> BOOLEAN]
    /\ paid_at    \in [Agents -> Nat]

(* ---------------------------------------------------------------------------
   Initial state — oracle fresh, no payments made
   --------------------------------------------------------------------------- *)

Init ==
    /\ oracle_age = 0
    /\ paid    = [a \in Agents |-> FALSE]
    /\ paid_at = [a \in Agents |-> 0]

(* ---------------------------------------------------------------------------
   Tick — oracle ages; clock advances toward and past the freshness window.
   --------------------------------------------------------------------------- *)

Tick ==
    /\ oracle_age < MaxAge
    /\ oracle_age' = oracle_age + 1
    /\ UNCHANGED <<paid, paid_at>>

(* ---------------------------------------------------------------------------
   PayBuggy(a) — buggy settlement: pays without checking oracle freshness.
   Records oracle_age at payment time so StaleDataRejected can detect the bug.
   The omitted guard is: oracle_age <= FRESHNESS.
   --------------------------------------------------------------------------- *)

PayBuggy(a) ==
    /\ a \in Agents
    /\ ~paid[a]                                       \* not yet paid
    /\ oracle_age > 0                                 \* at least one Tick occurred
    /\ paid'    = [paid    EXCEPT ![a] = TRUE]
    /\ paid_at' = [paid_at EXCEPT ![a] = oracle_age] \* record oracle age at settlement
    /\ UNCHANGED oracle_age

(* ---------------------------------------------------------------------------
   PayCorrect(a) — correct settlement: rejects stale oracle data.
   Defined for comparison; Next uses PayBuggy so TLC finds the violation.
   --------------------------------------------------------------------------- *)

PayCorrect(a) ==
    /\ a \in Agents
    /\ ~paid[a]
    /\ oracle_age > 0
    /\ oracle_age <= FRESHNESS                        \* freshness guard (the fix)
    /\ paid'    = [paid    EXCEPT ![a] = TRUE]
    /\ paid_at' = [paid_at EXCEPT ![a] = oracle_age]
    /\ UNCHANGED oracle_age

(* ---------------------------------------------------------------------------
   State machine
   --------------------------------------------------------------------------- *)

Next ==
    \/ (\E a \in Agents : PayBuggy(a))
    \/ Tick

Fairness ==
    \A a \in Agents : WF_vars(PayBuggy(a))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy payment violates.
   =========================================================================== *)

(*
 * Payment must only settle against fresh oracle data.
 * Violated by: Init → Tick → Tick → PayBuggy(a1)
 *   oracle_age = 2 when PayBuggy fires, FRESHNESS = 1.
 *   paid_at[a1] = 2 > FRESHNESS  ⟹  StaleDataRejected violated.
 *)
StaleDataRejected ==
    \A a \in Agents : paid[a] => paid_at[a] <= FRESHNESS

=============================================================================
