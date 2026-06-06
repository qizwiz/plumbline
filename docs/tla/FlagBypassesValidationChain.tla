--------------------------- MODULE FlagBypassesValidationChain ---------------------------
(*
 * Formal specification of plumbline's FlagBypassesValidationChain FailureMode.
 *
 * The bug class: a signature validator OR auth gate runs an enforcement
 * step only when a CALLER-SUPPLIED BOOLEAN flag is true. The flag is
 * carried in the signature payload itself (or in calldata under the
 * attacker's control), so the attacker simply sets the flag to false
 * and the enforcement step is skipped. The signature is accepted even
 * though the wallet config REQUIRED the enforcement.
 *
 * Structural shape: "flag-bypasses-validation-chain." The guard exists
 * AND is correctly positioned AND has the right identity binding —
 * but it is GATED on an attacker-controlled boolean. Setting the
 * boolean to FALSE skips the gate entirely.
 *
 * Distinct from:
 *  - SignatureReplay (no guard at all)
 *  - ReentrancyDrain (guard misplaced)
 *  - ERC4337StaticSigDoS (caller-bound auth misread)
 *  - PartialSignatureReplay (per-element guard without batch binding)
 *  - CrossWalletSigReplay (no wallet-identity binding)
 *  - Uint64FeeOverflow (narrow accumulator truncation)
 *  - Create2NonIdempotent (idempotency violation on retry)
 *
 * Concrete instance: Cantina sequence-v3 H-01, BaseSig's chained-
 * signature path branches on the `useCheckpointer` flag before the
 * checkpoint-enforcement call. An attacker constructs a chained
 * signature with useCheckpointer=false; the wallet still has a
 * checkpointer configured but the validation never runs. The signature
 * is accepted despite failing what the on-chain config requires.
 * (See examples/sequence/.ANSWERS.md H-01.)
 *
 * Generalizes to:
 *  - any "sandbox mode" feature flag that bypasses checks
 *  - "trusted path" boolean that skips identity verification
 *  - ERC-4626-style allowance-skipping flags
 *  - lazy-validation with attacker-settable "skip" parameters
 *
 * Architectural lineage:
 *  Ninth bug-class shape in the corpus. Authored after sequence H-01
 *  ran cold against the 8 existing shapes and none structurally fit.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config FlagBypassesValidationChain.cfg -deadlock FlagBypassesValidationChain
 *
 * Expected outcome: TLC reports invariant EnforcementHonored VIOLATED.
 * Counterexample: AcceptBuggy fires on a signature with the bypass flag
 * set true; the enforcement step did NOT run, but the signature was
 * accepted. State 2 shows the violation.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    NumSigs,          \* Number of signatures the attacker can submit
    NumWallets,       \* Number of wallets (each requires enforcement)
    MaxSteps          \* TLC bound

ASSUME NumSigs    \in Nat
ASSUME NumWallets \in Nat
ASSUME MaxSteps   \in Nat
ASSUME NumSigs > 0
ASSUME NumWallets > 0

Sigs    == 1..NumSigs
Wallets == 1..NumWallets

(* ---------------------------------------------------------------------------
   State variables

   accepted   — bool: signature s was accepted on wallet w
   enforced   — bool: the enforcement step was actually run for (s, w)
   step_count — TLC bound counter
   --------------------------------------------------------------------------- *)

VARIABLES
    accepted,
    enforced,
    step_count

vars == <<accepted, enforced, step_count>>

TypeInvariant ==
    /\ accepted   \in [Sigs \X Wallets -> BOOLEAN]
    /\ enforced   \in [Sigs \X Wallets -> BOOLEAN]
    /\ step_count \in Nat

(* ---------------------------------------------------------------------------
   Initial state — nothing accepted, nothing enforced
   --------------------------------------------------------------------------- *)

Init ==
    /\ accepted   = [pair \in Sigs \X Wallets |-> FALSE]
    /\ enforced   = [pair \in Sigs \X Wallets |-> FALSE]
    /\ step_count = 0

(* ---------------------------------------------------------------------------
   AcceptBuggy(s, w, bypass) — BUGGY validator.

   The wallet requires enforcement. The signature carries a boolean
   `bypass`. If bypass = TRUE, the validator SKIPS the enforcement step
   AND accepts. If bypass = FALSE, enforcement runs (and we model it as
   passing in this abstraction).

   The bug: an attacker simply sets bypass = TRUE in the signature.
   --------------------------------------------------------------------------- *)

AcceptBuggy(s, w, bypass) ==
    /\ s \in Sigs
    /\ w \in Wallets
    /\ bypass \in BOOLEAN
    /\ accepted[<<s, w>>] = FALSE
    /\ step_count < MaxSteps
    /\ accepted'   = [accepted   EXCEPT ![<<s, w>>] = TRUE]
    /\ enforced'   = [enforced   EXCEPT ![<<s, w>>] = ~bypass]
    /\ step_count' = step_count + 1

(* ---------------------------------------------------------------------------
   AcceptCorrect(s, w) — CORRECT validator.

   Enforcement ALWAYS runs before acceptance. There is no bypass flag.
   --------------------------------------------------------------------------- *)

AcceptCorrect(s, w) ==
    /\ s \in Sigs
    /\ w \in Wallets
    /\ accepted[<<s, w>>] = FALSE
    /\ step_count < MaxSteps
    /\ accepted'   = [accepted   EXCEPT ![<<s, w>>] = TRUE]
    /\ enforced'   = [enforced   EXCEPT ![<<s, w>>] = TRUE]
    /\ step_count' = step_count + 1

(* ---------------------------------------------------------------------------
   State machine
   --------------------------------------------------------------------------- *)

Next ==
    \E s \in Sigs : \E w \in Wallets : \E b \in BOOLEAN :
        AcceptBuggy(s, w, b)

Fairness ==
    \A s \in Sigs : \A w \in Wallets : \A b \in BOOLEAN :
        WF_vars(AcceptBuggy(s, w, b))

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT — every accepted signature must have its enforcement
   step actually run. The buggy validator violates it when bypass=TRUE.
   =========================================================================== *)

EnforcementHonored ==
    \A s \in Sigs : \A w \in Wallets :
        accepted[<<s, w>>] => enforced[<<s, w>>]

(* Sanity *)
StepCountBounded ==
    step_count <= NumSigs * NumWallets

(* ===========================================================================
   TEMPORAL — monotonic acceptance
   =========================================================================== *)

AcceptanceMonotonic ==
    [][\A s \in Sigs : \A w \in Wallets :
         accepted[<<s, w>>] => accepted'[<<s, w>>]]_accepted

=============================================================================
