----------------------- MODULE FirstDepositorInflation -----------------------
(****************************************************************************)
(*  Failure mode: first-depositor inflation via vested-rewards channel.     *)
(*                                                                          *)
(*  Pattern (banked from Sherlock 1259 DRE dreUSDs finding, 2026-06-08):    *)
(*                                                                          *)
(*    1. ERC-4626 vault uses _virtualBalance pattern to prevent inflation  *)
(*       via direct transfers (standard mitigation for decimalsOffset=0).  *)
(*    2. totalAssets() = _virtualBalance + rewardsDistributor.vestedAmount() *)
(*    3. Vesting amount grows over time WITHOUT state changes in vault.    *)
(*    4. Attacker deposits 1 wei first → gets 1 share.                     *)
(*    5. Admin adds rewards → vesting starts (e.g., 1000 dreUSD over 7d).  *)
(*    6. Time passes → vestedAmount climbs → totalAssets climbs.           *)
(*    7. Victim deposits X dreUSD → shares = X * 1 / (1 + vested).         *)
(*       If X << vested, shares rounds to 0 (or very small).               *)
(*    8. Both redeem: attacker captures ~half of (virtualBalance + vested),*)
(*       victim gets far less than deposited.                              *)
(*                                                                          *)
(*  Root cause: the vested-amount channel bypasses the _virtualBalance     *)
(*  mitigation. totalAssets() inflates WITHOUT proportional share minting. *)
(*                                                                          *)
(*  Mitigation: override _decimalsOffset() to ≥6; OR seed vault with       *)
(*  deployer deposit before rewards; OR enforce minimum shares-out > 0.    *)
(*                                                                          *)
(*  Severity: High (principal loss for legitimate depositors).             *)
(*                                                                          *)
(*  Concrete instance:                                                      *)
(*    corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd/test/    *)
(*    PoC_FirstDepositorInflation.t.sol                                     *)
(****************************************************************************)
EXTENDS Integers, FiniteSets, TLC

(* ---------------------------------------------------------------------------
   Constants
   --------------------------------------------------------------------------- *)

CONSTANTS
    Users,              \* Set of users: {Attacker, Victim}
    FirstDepositAmount, \* Nat: attacker's tiny first deposit (e.g., 1)
    VictimDepositAmount,\* Nat: victim's normal deposit (e.g., 500)
    RewardAmount,       \* Nat: admin adds this much to vesting (e.g., 1000)
    VestPeriod,         \* Nat: rewards vest over this many time units
    MaxTime             \* Nat: TLC bound on time advancement

ASSUME IsFiniteSet(Users)
ASSUME Cardinality(Users) = 2
ASSUME FirstDepositAmount \in Nat
ASSUME VictimDepositAmount \in Nat
ASSUME RewardAmount \in Nat
ASSUME VestPeriod \in Nat
ASSUME MaxTime \in Nat
ASSUME FirstDepositAmount > 0
ASSUME VictimDepositAmount > 0
ASSUME RewardAmount > 0
ASSUME VestPeriod > 0
ASSUME MaxTime >= VestPeriod

\* Helper: extract the two users
Attacker == CHOOSE u \in Users : TRUE
Victim   == CHOOSE u \in Users : u # Attacker

(* ---------------------------------------------------------------------------
   State variables
   --------------------------------------------------------------------------- *)

VARIABLES
    time,               \* Nat: current block timestamp
    virtualBalance,     \* Nat: vault's internal balance (updated on deposit/redeem)
    totalSupply,        \* Nat: total shares outstanding
    userShares,         \* function Users -> Nat: shares held per user
    userDeposited,      \* function Users -> Nat: cumulative assets deposited
    userRedeemed,       \* function Users -> Nat: cumulative assets redeemed
    rewardsPending,     \* Nat: total rewards added (constant once set)
    vestStart,          \* Nat: vesting start time
    vestEnd             \* Nat: vesting end time

vars == << time, virtualBalance, totalSupply, userShares, userDeposited,
           userRedeemed, rewardsPending, vestStart, vestEnd >>

(* ---------------------------------------------------------------------------
   Helpers
   --------------------------------------------------------------------------- *)

\* vestedAmount mimics IdreRewardsDistributor.vestedAmount()
\* Returns how much has vested so far
VestedAmount ==
    IF rewardsPending = 0 \/ vestEnd = vestStart
    THEN 0
    ELSE LET tEff == IF time < vestEnd THEN time ELSE vestEnd
             elapsed == tEff - vestStart
         IN (elapsed * rewardsPending) \div VestPeriod

\* totalAssets mimics dreUSDs.totalAssets() = _virtualBalance + vestedAmount()
TotalAssets == virtualBalance + VestedAmount

(* ---------------------------------------------------------------------------
   Type invariant
   --------------------------------------------------------------------------- *)

TypeInvariant ==
    /\ time \in Nat
    /\ virtualBalance \in Nat
    /\ totalSupply \in Nat
    /\ userShares \in [Users -> Nat]
    /\ userDeposited \in [Users -> Nat]
    /\ userRedeemed \in [Users -> Nat]
    /\ rewardsPending \in Nat
    /\ vestStart \in Nat
    /\ vestEnd \in Nat

(* ---------------------------------------------------------------------------
   Initial state
   --------------------------------------------------------------------------- *)

Init ==
    /\ time = 0
    /\ virtualBalance = 0
    /\ totalSupply = 0
    /\ userShares = [u \in Users |-> 0]
    /\ userDeposited = [u \in Users |-> 0]
    /\ userRedeemed = [u \in Users |-> 0]
    /\ rewardsPending = 0
    /\ vestStart = 0
    /\ vestEnd = 0

(* ---------------------------------------------------------------------------
   Actions
   --------------------------------------------------------------------------- *)

\* Attacker makes the FIRST deposit (tiny amount to get shares 1:1)
AttackerFirstDeposit ==
    /\ totalSupply = 0                      \* must be first
    /\ userDeposited[Attacker] = 0          \* attacker hasn't deposited yet
    /\ LET shares == FirstDepositAmount     \* 1:1 for first deposit
       IN
           /\ virtualBalance' = virtualBalance + FirstDepositAmount
           /\ totalSupply' = totalSupply + shares
           /\ userShares' = [userShares EXCEPT ![Attacker] = shares]
           /\ userDeposited' = [userDeposited EXCEPT ![Attacker] = FirstDepositAmount]
           /\ UNCHANGED << time, userRedeemed, rewardsPending, vestStart, vestEnd >>

\* Admin adds rewards — starts vesting schedule
AddRewards ==
    /\ rewardsPending = 0                   \* only once
    /\ totalSupply > 0                      \* after attacker deposited
    /\ rewardsPending' = RewardAmount
    /\ vestStart' = time
    /\ vestEnd' = time + VestPeriod
    /\ UNCHANGED << time, virtualBalance, totalSupply, userShares,
                   userDeposited, userRedeemed >>

\* Time passes — allows vesting to accrue
Tick ==
    /\ time < MaxTime
    /\ time' = time + 1
    /\ UNCHANGED << virtualBalance, totalSupply, userShares, userDeposited,
                   userRedeemed, rewardsPending, vestStart, vestEnd >>

\* Victim deposits (gets shares based on INFLATED totalAssets)
VictimDeposit ==
    /\ userDeposited[Victim] = 0            \* victim hasn't deposited yet
    /\ totalSupply > 0                      \* attacker already deposited
    /\ rewardsPending > 0                   \* rewards are vesting
    /\ LET ta == TotalAssets
           \* ERC4626 deposit formula: shares = assets * totalSupply / totalAssets
           shares == (VictimDepositAmount * totalSupply) \div ta
       IN
           /\ virtualBalance' = virtualBalance + VictimDepositAmount
           /\ totalSupply' = totalSupply + shares
           /\ userShares' = [userShares EXCEPT ![Victim] = shares]
           /\ userDeposited' = [userDeposited EXCEPT ![Victim] = VictimDepositAmount]
           /\ UNCHANGED << time, userRedeemed, rewardsPending, vestStart, vestEnd >>

\* User redeems all their shares
\* ERC4626 redeem formula: assets = shares * totalAssets / totalSupply
Redeem(u) ==
    /\ userShares[u] > 0
    /\ userRedeemed[u] = 0                  \* hasn't redeemed yet
    /\ LET ta == TotalAssets
           assets == (userShares[u] * ta) \div totalSupply
           vested == VestedAmount
       IN
           /\ assets <= virtualBalance + vested    \* sufficient liquidity
           /\ virtualBalance' = virtualBalance + vested - assets
           /\ totalSupply' = totalSupply - userShares[u]
           /\ userShares' = [userShares EXCEPT ![u] = 0]
           /\ userRedeemed' = [userRedeemed EXCEPT ![u] = assets]
           /\ UNCHANGED << time, userDeposited, rewardsPending, vestStart, vestEnd >>

Next ==
    \/ AttackerFirstDeposit
    \/ AddRewards
    \/ Tick
    \/ VictimDeposit
    \/ \E u \in Users : Redeem(u)

Spec == Init /\ [][Next]_vars

(* ---------------------------------------------------------------------------
   INVARIANTS / SAFETY PROPERTIES
   --------------------------------------------------------------------------- *)

\* The core bug: attacker's share of redemptions should NOT exceed their fair
\* share of total deposits + rewards.
\* 
\* Fair share calculation:
\*   Total capital = AttackerDeposit + VictimDeposit + Rewards
\*   Attacker's fair share = (AttackerDeposit / (AttackerDeposit + VictimDeposit)) * Total
\*
\* The bug: attacker redeems MORE than this fair share by inflating share price
\* before victim deposits.

ShareInflationBounded ==
    LET totalCapital == userDeposited[Attacker] + userDeposited[Victim] + rewardsPending
        attackerContrib == userDeposited[Attacker]
        victimContrib == userDeposited[Victim]
        totalContrib == attackerContrib + victimContrib
        attackerFairShare == IF totalContrib = 0
                              THEN 0
                              ELSE (attackerContrib * totalCapital) \div totalContrib
        \* Allow small rounding tolerance (1 unit)
        maxLegitRedemption == attackerFairShare + 1
    IN
        \/ totalContrib = 0                              \* no deposits yet
        \/ userRedeemed[Attacker] <= maxLegitRedemption  \* attacker within bounds

==============================================================================
(* Counterexample (TLC discharge):
   
State 1: Init — vault empty
State 2: AttackerFirstDeposit — attacker deposits 1, gets 1 share
State 3: AddRewards — admin adds 1000 rewards vesting over 7 time units
State 4: Tick — time advances to 1, vestedAmount = 1000*1/7 ≈ 142
State 5: VictimDeposit — victim deposits 500, totalAssets = 1+142 = 143
         victim gets shares = 500*1/143 = 3 (massive rounding down!)
State 6: Redeem(Attacker) — attacker redeems 1 share for 1*(501+142)/4 = 160
         Attacker paid 1, received 160 → net profit 159
         Fair share = 1/(1+500) * 1501 ≈ 3, but attacker got 160!
         
INVARIANT VIOLATED: ShareInflationBounded fails at State 6.
*)
