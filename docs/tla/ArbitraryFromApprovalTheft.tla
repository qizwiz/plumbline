---------------------------- MODULE ArbitraryFromApprovalTheft ----------------------------
(*
 * Failure mode: ARBITRARY-FROM-ADDRESS WITH EXISTING-APPROVAL EXPLOITATION
 *
 * The bug class: a token transfer/deposit function accepts a CALLER-SUPPLIED
 * `from` address parameter and does NOT validate that the caller is authorized
 * to move tokens on behalf of that address. Instead, it relies solely on the
 * ERC-20 transferFrom allowance mechanism. An attacker can exploit this by
 * specifying a victim address that has previously granted token approval to
 * the contract. The contract will successfully transfer tokens from the victim
 * to itself (or another destination), even though the victim never authorized
 * THIS PARTICULAR TRANSACTION. The victim's tokens are stolen simply because
 * they had set an allowance for a different, legitimate purpose.
 *
 * Concrete instance: examples/boss-bridge/.ANSWERS.md H-1
 *   "Users who give tokens approvals to L1BossBridge may have those assets stolen.
 *    The depositTokensToL2 function allows anyone to call it with a `from` address
 *    of any account that has approved tokens to the bridge."
 *
 * Structural shape:
 *   - Function takes `from` parameter (caller-controlled)
 *   - No authorization check (msg.sender == from, signature, etc.)
 *   - Calls token.transferFrom(from, destination, amount)
 *   - Victim has pre-existing approval to contract
 *   - Attacker can drain victim by passing victim address as `from`
 *
 * Attack requirements:
 *   1. Victim has called token.approve(contract, amount) where amount > 0
 *   2. Contract exposes a function with caller-controlled `from` parameter
 *   3. No check that msg.sender is authorized to act as `from`
 *   4. Attacker calls function with from=victim, destination=attacker
 *
 * TLC finds: attacker drains victim's approved tokens in ≤5 states
 *)

EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    Accounts,       \* {victim, attacker, contract}
    MaxTokens       \* max tokens for bounded model checking (e.g., 3)

VARIABLES
    balances,       \* balances[acct] = token balance
    allowances,     \* allowances[owner][spender] = approved amount
    destinationBal, \* tracks attacker's effective destination balance
    pc              \* {"init", "approved", "exploited"}

vars == <<balances, allowances, destinationBal, pc>>

TypeOK ==
    /\ balances \in [Accounts -> 0..MaxTokens]
    /\ allowances \in [Accounts -> [Accounts -> 0..MaxTokens]]
    /\ destinationBal \in 0..MaxTokens
    /\ pc \in {"init", "approved", "exploited"}

Init ==
    /\ balances = [a \in Accounts |-> 
         IF a = "victim" THEN MaxTokens ELSE 0]
    /\ allowances = [owner \in Accounts |-> 
         [spender \in Accounts |-> 0]]
    /\ destinationBal = 0
    /\ pc = "init"

\* Victim approves contract for legitimate purpose (e.g., future deposit)
VictimApproves ==
    /\ pc = "init"
    /\ balances["victim"] > 0
    /\ allowances' = [allowances EXCEPT !["victim"]["contract"] = balances["victim"]]
    /\ pc' = "approved"
    /\ UNCHANGED <<balances, destinationBal>>

\* Attacker calls depositTokensToL2(from=victim, l2Recipient=attacker, amount)
\* The contract does transferFrom(victim, contract, amount) without checking authorization
AttackerExploitsArbitraryFrom ==
    /\ pc = "approved"
    /\ allowances["victim"]["contract"] > 0
    /\ LET amount == allowances["victim"]["contract"] IN
       /\ balances["victim"] >= amount
       /\ balances' = [balances EXCEPT 
            !["victim"] = @ - amount,
            !["contract"] = @ + amount]
       /\ allowances' = [allowances EXCEPT 
            !["victim"]["contract"] = @ - amount]
       /\ destinationBal' = destinationBal + amount
       /\ pc' = "exploited"

Next ==
    \/ VictimApproves
    \/ AttackerExploitsArbitraryFrom

Spec == Init /\ [][Next]_vars

--------------------------------------------------------------------------------
(* SAFETY INVARIANTS *)

\* Victim's tokens should not be moved without victim-initiated action
VictimTokensSafe ==
    pc = "exploited" => balances["victim"] = MaxTokens

\* Attacker should not gain control of victim's tokens via destination balance
NoArbitraryFromTheft ==
    destinationBal = 0

================================================================================
