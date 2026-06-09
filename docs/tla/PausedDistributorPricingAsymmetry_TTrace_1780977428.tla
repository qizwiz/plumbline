---- MODULE PausedDistributorPricingAsymmetry_TTrace_1780977428 ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, PausedDistributorPricingAsymmetry, PausedDistributorPricingAsymmetry_TEConstants

_expression ==
    LET PausedDistributorPricingAsymmetry_TEExpression == INSTANCE PausedDistributorPricingAsymmetry_TEExpression
    IN PausedDistributorPricingAsymmetry_TEExpression!expression
----

_trace ==
    LET PausedDistributorPricingAsymmetry_TETrace == INSTANCE PausedDistributorPricingAsymmetry_TETrace
    IN PausedDistributorPricingAsymmetry_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        virtualBalance = (43)
        /\
        pauseFundsLost = (14)
        /\
        userWithdrawnAssets = ((a :> 57 @@ b :> 0))
        /\
        totalSupply = (50)
        /\
        vestEnd = (7)
        /\
        userShares = ((a :> 0 @@ b :> 50))
        /\
        vestStart = (0)
        /\
        time = (1)
        /\
        distributorPaused = (TRUE)
        /\
        rewardsRemaining = (100)
    )
----

_init ==
    /\ userShares = _TETrace[1].userShares
    /\ rewardsRemaining = _TETrace[1].rewardsRemaining
    /\ virtualBalance = _TETrace[1].virtualBalance
    /\ time = _TETrace[1].time
    /\ vestEnd = _TETrace[1].vestEnd
    /\ distributorPaused = _TETrace[1].distributorPaused
    /\ userWithdrawnAssets = _TETrace[1].userWithdrawnAssets
    /\ vestStart = _TETrace[1].vestStart
    /\ pauseFundsLost = _TETrace[1].pauseFundsLost
    /\ totalSupply = _TETrace[1].totalSupply
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ userShares  = _TETrace[i].userShares
        /\ userShares' = _TETrace[j].userShares
        /\ rewardsRemaining  = _TETrace[i].rewardsRemaining
        /\ rewardsRemaining' = _TETrace[j].rewardsRemaining
        /\ virtualBalance  = _TETrace[i].virtualBalance
        /\ virtualBalance' = _TETrace[j].virtualBalance
        /\ time  = _TETrace[i].time
        /\ time' = _TETrace[j].time
        /\ vestEnd  = _TETrace[i].vestEnd
        /\ vestEnd' = _TETrace[j].vestEnd
        /\ distributorPaused  = _TETrace[i].distributorPaused
        /\ distributorPaused' = _TETrace[j].distributorPaused
        /\ userWithdrawnAssets  = _TETrace[i].userWithdrawnAssets
        /\ userWithdrawnAssets' = _TETrace[j].userWithdrawnAssets
        /\ vestStart  = _TETrace[i].vestStart
        /\ vestStart' = _TETrace[j].vestStart
        /\ pauseFundsLost  = _TETrace[i].pauseFundsLost
        /\ pauseFundsLost' = _TETrace[j].pauseFundsLost
        /\ totalSupply  = _TETrace[i].totalSupply
        /\ totalSupply' = _TETrace[j].totalSupply

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("PausedDistributorPricingAsymmetry_TTrace_1780977428.json", _TETrace)

=============================================================================

 Note that you can extract this module `PausedDistributorPricingAsymmetry_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `PausedDistributorPricingAsymmetry_TEExpression.tla` file takes precedence 
  over the module `PausedDistributorPricingAsymmetry_TEExpression` below).

---- MODULE PausedDistributorPricingAsymmetry_TEExpression ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, PausedDistributorPricingAsymmetry, PausedDistributorPricingAsymmetry_TEConstants

expression == 
    [
        \* To hide variables of the `PausedDistributorPricingAsymmetry` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        userShares |-> userShares
        ,rewardsRemaining |-> rewardsRemaining
        ,virtualBalance |-> virtualBalance
        ,time |-> time
        ,vestEnd |-> vestEnd
        ,distributorPaused |-> distributorPaused
        ,userWithdrawnAssets |-> userWithdrawnAssets
        ,vestStart |-> vestStart
        ,pauseFundsLost |-> pauseFundsLost
        ,totalSupply |-> totalSupply
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_userSharesUnchanged |-> userShares = userShares'
        
        \* Format the `userShares` variable as Json value.
        \* ,_userSharesJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(userShares)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_userSharesModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].userShares # _TETrace[s-1].userShares
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE PausedDistributorPricingAsymmetry_TETrace ----
\*EXTENDS IOUtils, TLC, PausedDistributorPricingAsymmetry, PausedDistributorPricingAsymmetry_TEConstants
\*
\*trace == IODeserialize("PausedDistributorPricingAsymmetry_TTrace_1780977428.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE PausedDistributorPricingAsymmetry_TETrace ----
EXTENDS TLC, PausedDistributorPricingAsymmetry, PausedDistributorPricingAsymmetry_TEConstants

trace == 
    <<
    ([virtualBalance |-> 100,pauseFundsLost |-> 0,userWithdrawnAssets |-> (a :> 0 @@ b :> 0),totalSupply |-> 100,vestEnd |-> 0,userShares |-> (a :> 50 @@ b :> 50),vestStart |-> 0,time |-> 0,distributorPaused |-> FALSE,rewardsRemaining |-> 0]),
    ([virtualBalance |-> 100,pauseFundsLost |-> 0,userWithdrawnAssets |-> (a :> 0 @@ b :> 0),totalSupply |-> 100,vestEnd |-> 7,userShares |-> (a :> 50 @@ b :> 50),vestStart |-> 0,time |-> 0,distributorPaused |-> FALSE,rewardsRemaining |-> 100]),
    ([virtualBalance |-> 100,pauseFundsLost |-> 0,userWithdrawnAssets |-> (a :> 0 @@ b :> 0),totalSupply |-> 100,vestEnd |-> 7,userShares |-> (a :> 50 @@ b :> 50),vestStart |-> 0,time |-> 1,distributorPaused |-> FALSE,rewardsRemaining |-> 100]),
    ([virtualBalance |-> 100,pauseFundsLost |-> 0,userWithdrawnAssets |-> (a :> 0 @@ b :> 0),totalSupply |-> 100,vestEnd |-> 7,userShares |-> (a :> 50 @@ b :> 50),vestStart |-> 0,time |-> 1,distributorPaused |-> TRUE,rewardsRemaining |-> 100]),
    ([virtualBalance |-> 43,pauseFundsLost |-> 0,userWithdrawnAssets |-> (a :> 57 @@ b :> 0),totalSupply |-> 50,vestEnd |-> 7,userShares |-> (a :> 0 @@ b :> 50),vestStart |-> 0,time |-> 1,distributorPaused |-> TRUE,rewardsRemaining |-> 100]),
    ([virtualBalance |-> 43,pauseFundsLost |-> 14,userWithdrawnAssets |-> (a :> 57 @@ b :> 0),totalSupply |-> 50,vestEnd |-> 7,userShares |-> (a :> 0 @@ b :> 50),vestStart |-> 0,time |-> 1,distributorPaused |-> TRUE,rewardsRemaining |-> 100])
    >>
----


=============================================================================

---- MODULE PausedDistributorPricingAsymmetry_TEConstants ----
EXTENDS PausedDistributorPricingAsymmetry

CONSTANTS a, b

=============================================================================

---- CONFIG PausedDistributorPricingAsymmetry_TTrace_1780977428 ----
CONSTANTS
    Users = { a , b }
    MaxTime = 7
    InitialDeposit = 100
    RewardAmount = 100
    VestPeriod = 7
    b = b
    a = a

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Mon Jun 08 22:57:08 CDT 2026