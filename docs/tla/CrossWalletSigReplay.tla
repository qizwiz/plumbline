--------------------------- MODULE CrossWalletSigReplay ---------------------------
(*
 * Formal specification of plumbline's CrossWalletSigReplay FailureMode.
 *
 * The bug class: a wallet authorizes off-chain signatures whose signed
 * payload OMITS the wallet's own identity (no `address(this)` in the
 * EIP-712 domain separator, no wallet address in the hashed payload).
 * As a result, two wallets that happen to share the same session
 * signer (or any common authorizer) will accept each other's
 * signatures — a signature created against wallet A is valid against
 * wallet B without modification.
 *
 * Structural shape: "no-identity-binding." The per-call guard exists
 * (signature must verify against the authorized signer) but the GROUP
 * CONTEXT — which wallet the signature was for — is not bound into
 * the signed material. The same authorizer therefore implicitly
 * authorizes every wallet that registered them.
 *
 * Distinct from:
 *  - SignatureReplay (no guard at all — here the guard exists but lacks
 *    identity binding)
 *  - ERC4337StaticSigDoS (caller-bound identity misread via EntryPoint —
 *    here the identity isn't bound at all)
 *  - PartialSignatureReplay (per-element guard without GROUP binding,
 *    where group = batch — here the missing binding is wallet identity,
 *    a global identity rather than a session-local one)
 *
 * Concrete instance: Cantina sequence-v3 M-01, SessionManager derives
 * the signing payload from session config + call data without including
 * `address(this)` in the EIP-712 domain or hashed payload, so the
 * signature is wallet-independent.
 * (See examples/sequence/.ANSWERS.md M-01.)
 *
 * Models two wallets sharing the same session signer. A signature
 * crafted against wallet A is submitted to wallet B; the buggy
 * validator does not check that the signed payload commits to
 * `address(this)`, so it accepts.
 *
 * Architectural lineage:
 *   Eighth bug-class shape in the corpus (was 7 entering this session).
 *   Authored after sequence M-01 was surfaced by ENSEMBLE.goal.md run
 *   data — none of the 7 existing shapes structurally fit.
 *
 * To check with TLC:
 *   cd docs/tla
 *   java -XX:+UseParallelGC -jar tla2tools.jar \
 *     -config CrossWalletSigReplay.cfg -deadlock CrossWalletSigReplay
 *
 * Expected outcome: TLC reports invariant WalletIdentityBound VIOLATED.
 * The counterexample: a signature whose `signed_for_wallet` is wallet
 * 1 is accepted by wallet 2, executing under wallet 2's context.
 *)

EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    NumWallets,       \* Number of wallets sharing the session signer.
                      \* Modeled as scalars 1..NumWallets to keep .cfg
                      \* grammar simple (no function literals in .cfg).
    NumSigs,          \* Number of distinct signatures crafted off-chain.
                      \* Each signature signed_for a specific wallet at
                      \* creation time.
    MaxExecs          \* Bound for TLC

ASSUME NumWallets \in Nat
ASSUME NumSigs    \in Nat
ASSUME MaxExecs   \in Nat
ASSUME NumWallets > 0
ASSUME NumSigs > 0

Wallets == 1..NumWallets
Sigs    == 1..NumSigs

(* Each signature was crafted for a specific wallet identity. The
 * attacker possesses sigs from wallet A; the bug fires when those sigs
 * are accepted at wallet B (b /= signed_for_wallet(s)).
 *
 * SignedForWallet(s) == s — each signature crafted for its
 * same-numbered wallet (cycling if NumSigs > NumWallets).
 * Specifically: SignedForWallet(s) == 1 + ((s - 1) mod NumWallets) *)
SignedForWallet(s) == 1 + ((s - 1) % NumWallets)

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    executed,             \* function (Sigs \X Wallets) -> BOOLEAN:
                          \* did signature s execute on wallet w?
    execs_total           \* Nat: total executions (TLC bound)

vars == <<executed, execs_total>>

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ executed     \in [Sigs \X Wallets -> BOOLEAN]
    /\ execs_total  \in Nat

(* ---------------------------------------------------------------------------
   Initial state
   --------------------------------------------------------------------------- *)

Init ==
    /\ executed     = [pair \in Sigs \X Wallets |-> FALSE]
    /\ execs_total  = 0

(* ---------------------------------------------------------------------------
   AcceptBuggy(s, w) — the BUGGY validator.
   Accepts signature s on wallet w as long as the signer authorized it.
   Does NOT check that the signed payload commits to w (omits
   `address(this)` from domain). Therefore any signature from any
   "registered signer" is accepted by any wallet that registered them.
   --------------------------------------------------------------------------- *)

AcceptBuggy(s, w) ==
    /\ s \in Sigs
    /\ w \in Wallets
    /\ executed[<<s, w>>] = FALSE
    /\ execs_total < MaxExecs
    /\ executed' = [executed EXCEPT ![<<s, w>>] = TRUE]
    /\ execs_total' = execs_total + 1

(* ---------------------------------------------------------------------------
   AcceptCorrect(s, w) — the CORRECT validator.
   Adds the identity-binding check: signature s only executes on its
   signed_for wallet.
   --------------------------------------------------------------------------- *)

AcceptCorrect(s, w) ==
    /\ s \in Sigs
    /\ w \in Wallets
    /\ executed[<<s, w>>] = FALSE
    /\ w = SignedForWallet(s)            \* identity binding check
    /\ execs_total < MaxExecs
    /\ executed' = [executed EXCEPT ![<<s, w>>] = TRUE]
    /\ execs_total' = execs_total + 1

(* ---------------------------------------------------------------------------
   State machine + fairness
   --------------------------------------------------------------------------- *)

Next == \E s \in Sigs : \E w \in Wallets : AcceptBuggy(s, w)

Fairness == \A s \in Sigs : \A w \in Wallets : WF_vars(AcceptBuggy(s, w))

\* Re-stated existence vs forall nesting kept in single line above
\* to satisfy single-binder quantifier grammar.

Spec == Init /\ [][Next]_vars /\ Fairness

(* ===========================================================================
   THE INVARIANT THAT MUST HOLD — and that the buggy validator violates.
   ===========================================================================

 * The validator PROMISES: signature s only executes on the wallet it
 * was signed for. Concretely: executed[s, w] => w = SignedForWallet(s).
 * The buggy validator omits the binding check, so signature 1 (signed
 * for wallet 1) can execute on wallet 2 — counterexample at state 2:
 * AcceptBuggy(s=1, w=2) sets executed[1, 2] = TRUE, but
 * SignedForWallet(1) = 1 # 2.
 *)
WalletIdentityBound ==
    \A s \in Sigs : \A w \in Wallets :
        executed[<<s, w>>] => (w = SignedForWallet(s))

(* Sanity: execution count tracks the executed table *)
ExecCountConsistent ==
    execs_total <= NumSigs * NumWallets

(* ===========================================================================
   TEMPORAL PROPERTIES
   =========================================================================== *)

(* Executions are monotonic — never unexecuted *)
ExecutionMonotonic ==
    [][\A s \in Sigs : \A w \in Wallets :
         executed[<<s, w>>] => executed'[<<s, w>>]]_executed

=============================================================================
