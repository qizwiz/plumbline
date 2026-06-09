---------------- MODULE PausedDistributorPricingAsymmetry ----------------
(***************************************************************************)
(*  Failure mode: vesting-vault share-price asymmetry when reward            *)
(*  distributor is paused but vault is NOT.                                  *)
(*                                                                           *)
(*  Pattern (banked from Sherlock 1259 DRE M-1 candidate, 2026-06-09):       *)
(*                                                                           *)
(*    1. Vault.totalAssets() = virtualBalance + distributor.vestedAmount()   *)
(*    2. distributor.vestedAmount() grows over time (no pause check on view) *)
(*    3. distributor.claimVested() reverts/returns 0 when paused             *)
(*    4. While paused: totalAssets keeps rising, virtualBalance stays flat   *)
(*    5. Early withdrawer prices against inflated totalAssets, drains the    *)
(*       (smaller) actual virtualBalance pool                                *)
(*    6. Late withdrawer cannot withdraw — assets > virtualBalance →         *)
(*       underflow on virtualBalance -= assets → revert                      *)
(*    7. Late withdrawer's principal is locked until unpause                 *)
(*                                                                           *)
(*  Maps to Sherlock V2 Medium rubric: user-vs-user fund redistribution      *)
(*  during legitimate pause action (carve-in not admin-trust).               *)
(*                                                                           *)
(*  Corpus precedents (plumbline NN search 2026-06-09):                      *)
(*    - "Inability to withdraw funds for certain users due to                 *)
(*       whenNotPaused modifier" — Sherlock M, cos=0.799                    *)
(*    - "User could withdraw more than supposed to, forcing last user        *)
(*       withdraw to fail" — C4 H, cos=0.789                                *)
(*    - "Share 1:1 Conversion, if vault incurs a loss, the last user to     *)
(*       withdraw is shortchanged" — Sherlock M, cos=0.816                  *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Users, MaxTime, InitialDeposit, RewardAmount, VestPeriod

VARIABLES
    time,                  \* current block.timestamp
    distributorPaused,     \* boolean: distributor pause state
    virtualBalance,        \* vault's tracked balance (only updated on real ops)
    totalSupply,           \* shares outstanding
    rewardsRemaining,      \* unvested rewards still in distributor
    vestStart,             \* cTs in dreRewardsDistributor
    vestEnd,               \* eTs in dreRewardsDistributor
    userShares,            \* shares per user
    userWithdrawnAssets,   \* assets each user has redeemed (cumulative)
    pauseFundsLost         \* invariant tracker: cumulative loss attributable to paused-pricing

vars == << time, distributorPaused, virtualBalance, totalSupply,
           rewardsRemaining, vestStart, vestEnd, userShares,
           userWithdrawnAssets, pauseFundsLost >>

(* --- Helpers --- *)

VestedAmount ==
    IF rewardsRemaining = 0 \/ vestEnd = vestStart
    THEN 0
    ELSE LET tEff == IF time < vestEnd THEN time ELSE vestEnd
             elapsed == tEff - vestStart
         IN (elapsed * rewardsRemaining) \div (vestEnd - vestStart)

TotalAssets == virtualBalance + VestedAmount

SharePrice(u) ==
    IF totalSupply = 0
    THEN 1
    ELSE (TotalAssets * userShares[u]) \div totalSupply

(* --- Init --- *)

Init ==
    /\ time = 0
    /\ distributorPaused = FALSE
    /\ virtualBalance = InitialDeposit
    /\ totalSupply = InitialDeposit  \* 1:1 first depositors
    /\ rewardsRemaining = 0
    /\ vestStart = 0
    /\ vestEnd = 0
    /\ userShares = [u \in Users |-> InitialDeposit \div Cardinality(Users)]
    /\ userWithdrawnAssets = [u \in Users |-> 0]
    /\ pauseFundsLost = 0

(* --- Actions --- *)

\* admin adds vesting rewards (assumed once for simplicity)
AddRewards ==
    /\ rewardsRemaining = 0
    /\ ~distributorPaused
    /\ rewardsRemaining' = RewardAmount
    /\ vestStart' = time
    /\ vestEnd' = time + VestPeriod
    /\ UNCHANGED << time, distributorPaused, virtualBalance, totalSupply,
                   userShares, userWithdrawnAssets, pauseFundsLost >>

\* time passes
Tick ==
    /\ time < MaxTime
    /\ time' = time + 1
    /\ UNCHANGED << distributorPaused, virtualBalance, totalSupply,
                   rewardsRemaining, vestStart, vestEnd, userShares,
                   userWithdrawnAssets, pauseFundsLost >>

\* PAUSER pauses the distributor (NOT the vault)
PauseDistributor ==
    /\ ~distributorPaused
    /\ distributorPaused' = TRUE
    /\ UNCHANGED << time, virtualBalance, totalSupply, rewardsRemaining,
                   vestStart, vestEnd, userShares, userWithdrawnAssets,
                   pauseFundsLost >>

\* PAUSER unpauses (sometime later)
UnpauseDistributor ==
    /\ distributorPaused
    /\ distributorPaused' = FALSE
    /\ UNCHANGED << time, virtualBalance, totalSupply, rewardsRemaining,
                   vestStart, vestEnd, userShares, userWithdrawnAssets,
                   pauseFundsLost >>

\* User withdraws ALL shares.
\* In the buggy model: assets priced via TotalAssets (which includes phantom vested when paused)
\* In the fixed model: claimVestedRewards always flushes vested to virtualBalance before redeem
UserWithdraw(u) ==
    LET assetsOwed == IF totalSupply = 0
                      THEN 0
                      ELSE (TotalAssets * userShares[u]) \div totalSupply
        claimable == IF distributorPaused
                     THEN 0  \* paused — claim returns 0, virtualBalance stays
                     ELSE VestedAmount  \* claimed and added to virtualBalance
        newVirtualBalance == virtualBalance + claimable
    IN
        /\ userShares[u] > 0
        /\ IF assetsOwed <= newVirtualBalance
           THEN
               \* successful withdraw
               /\ virtualBalance' = newVirtualBalance - assetsOwed
               /\ totalSupply' = totalSupply - userShares[u]
               /\ rewardsRemaining' = rewardsRemaining - claimable
               /\ userShares' = [userShares EXCEPT ![u] = 0]
               /\ userWithdrawnAssets' = [userWithdrawnAssets EXCEPT ![u] = @ + assetsOwed]
               /\ UNCHANGED << time, distributorPaused, vestStart, vestEnd,
                              pauseFundsLost >>
           ELSE
               \* withdraw REVERTS (underflow on virtualBalance -= assets)
               \* track this as funds-not-receivable (loss while paused window holds)
               /\ pauseFundsLost' = pauseFundsLost + (assetsOwed - newVirtualBalance)
               /\ UNCHANGED << time, distributorPaused, virtualBalance,
                              totalSupply, rewardsRemaining, vestStart, vestEnd,
                              userShares, userWithdrawnAssets >>

Next ==
    \/ AddRewards
    \/ Tick
    \/ PauseDistributor
    \/ UnpauseDistributor
    \/ \E u \in Users : UserWithdraw(u)

Spec == Init /\ [][Next]_vars

(* --- INVARIANTS / SAFETY PROPERTIES --- *)

\* Stated DRE invariant: share price must only increase or stay flat (rounding dust ok).
\* In TotalAssets/totalSupply terms, this holds in the model.
\* But the REALIZED per-user share value can DECREASE for late withdrawers during pause.

(* Bug witness: there exists a state where a user CANNOT withdraw their *)
(* full-priced share allocation despite having shares.                  *)
NoStrandedUser ==
    \A u \in Users :
        userShares[u] = 0 \/ pauseFundsLost = 0

(* Bug witness: share-realization asymmetry between early and late      *)
(* withdrawers in the same vesting cohort.                              *)
NoWithdrawalAsymmetry ==
    \A u1, u2 \in Users :
        (userShares[u1] = 0 /\ userShares[u2] = 0 /\ u1 # u2) =>
            \* If both fully withdrew, their assets-per-original-share should differ by < 1
            \* (rounding dust only). Otherwise, asymmetry — invariant violated.
            userWithdrawnAssets[u1] = userWithdrawnAssets[u2]

(* PRIMARY safety violation that TLC will find counterexample for: *)
ShareValuePreserved == pauseFundsLost = 0

============================================================================
\* TLC config (PausedDistributorPricingAsymmetry.cfg):
\*   CONSTANTS
\*     Users = {a, b}
\*     MaxTime = 14
\*     InitialDeposit = 100
\*     RewardAmount = 100
\*     VestPeriod = 7
\*   SPECIFICATION Spec
\*   INVARIANT ShareValuePreserved
\*   \* Expected: TLC finds counterexample trace: deposit -> addRewards ->
\*   \* tick ~3 -> pause -> userA withdraws (succeeds at inflated price) ->
\*   \* userB withdraws (fails — pauseFundsLost > 0) -> INVARIANT VIOLATED.
