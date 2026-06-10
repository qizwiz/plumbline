# Pass A annotation sample (N=50, seed=42)

Generated 2026-06-09 by tools/annotate_corpus_invariants.py.

## Summary

- **Clean** (extracted + adversarial critic accepted): 7 / 50
- **Refuted** by adversarial critic: 43 / 50
- **Null** (extraction self-reported `category: none`): 0 / 50

If refuted ratio > 30%: the extraction prompt needs work before running --full.

Review each row: does the extracted structural_invariant faithfully capture the bug? Does the critic's REFUTE decision look right?

---

## 1. 🔴 REFUTED — [M] Version hash is not correctly enforced in code unpacker

- Corpus: `2023-10-zksync` (source: c4)
- Body: **Mitigation:** `version_hash_matches.conditionally_enforce_true(cs, state.state_get_from_queue);`

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "version_hash_enforced_on_dequeue",
      "solidity_expr": "state_get_from_queue == false || version_hash_matches == true",
      "quantities_involved": [
        "version_hash_matches",
        "state_get_from_queue"
      ],
      "violation_pattern": "code unpacker accepts mismatched version hash when dequeuing from state; attacker can inject arbitrary bytecode without validation",
      "actions_required": [
        "unpack_code"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariant could hold even when the bug fires because the bug is about conditional enforcement (only enforcing when state_get_from_queue is true), but the extracted invariant expresses exactly that conditional logic, meaning it describes the intended behavior rather than capturing what the buggy "
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant could hold even when the bug fires because the bug is about conditional enforcement (only enforcing when state_get_from_queue is true), but the extracted invariant expresses exactly that conditional logic, meaning it describes the intended behavior rather than capturing what the buggy *

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 2. 🔴 REFUTED — [H] Typo in PoolTemplate unlock function results in user being able to unlock multiple times

- Corpus: `2022-01-insure` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "replay_protection",
      "name": "user_can_unlock_at_most_once_per_lock",
      "solidity_expr": "unlocked[user][lockId] == true",
      "quantities_involved": [
        "unlocked",
        "user",
        "lockId",
        "userBalance"
      ],
      "violation_pattern": "typo in unlock function allows user to bypass state update marking lock as consumed, enabling repeated unlock calls for same lock",
      "actions_required": [
        "lock",
        "unlock",
        "unlock_replay"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 3"
      ]
    },
    {
      "category": "conservation",
      "name": "total_unlocked_equals_withdrawals",
      "solidity_expr": "sum_unlocked_by_all_users <= total_locked",
      "quantities_involved": [
        "totalLocked",
        "userBalance",
        "contractBalance"
      ],
      "violation_pattern": "repeated unlock calls allow user to withdraw more tokens than they locked, draining contract balance beyond their entitlement",
      "actions_required": [
        "lock",
        "unlock",
        "unlock_replay"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 3"
      ]
    },
    {
      "category": "monotonicity",
      "name": "user_balance_only_decreases_on_unlock",
      "solidity_expr": "userBalance_after <= userBalance_before",
      "quantities_involved": [
        "userBalance",
        "lockedAmount"
      ],
      "violation_pattern": "typo allows unlock to skip decrementing user balance or marking lock as used, violating monotonic decrease invariant",
      "actions_required": [
        "unlock"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The third invariant 'user_balance_only_decreases_on_unlock' claims userBalance should decrease on unlock, but if the typo allows skipping the balance decrement entirely, then this invariant could still hold vacuously (balance stays same or decreases to zero once) even when the bug fires and allows m"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The third invariant 'user_balance_only_decreases_on_unlock' claims userBalance should decrease on unlock, but if the typo allows skipping the balance decrement entirely, then this invariant could still hold vacuously (balance stays same or decreases to zero once) even when the bug fires and allows m*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 3. 🔴 REFUTED — [M] `ThrusterFactory.setYieldCut` should claim fees for all pools before

- Corpus: `2024-02-thruster` (source: c4)
- Body: **Mechanism:** Yield can be collected with wrong proportion.

**Mitigation:** I guess protocol just needs to acknowledge the issue as it will be not possible (not worthy) to implement such mechanism.

**[jooleseth (Thruster) acknowledged and commented](https://github.com/code-423n4/2024-02-thruster-findings/issues/12#issuecomment-1963667483):**
 > We acknowledge that this situation is possible, bu...

**Extracted invariant:**

```json
{
  "extractable": "PARTIAL",
  "driver_shape": "stateful_invariant",
  "resistant_reason": "requires_multi_tx_ordering",
  "structural_invariants": [
    {
      "category": "ordering",
      "name": "fee_distribution_rate_consistency",
      "solidity_expr": "accumulatedFees_before * newYieldCut == accumulatedFees_after * oldYieldCut",
      "quantities_involved": [
        "yieldCut",
        "accumulatedFees",
        "unclaimedYield"
      ],
      "violation_pattern": "setYieldCut changes fee split ratio before claiming accrued fees; unclaimed fees are then distributed under new proportion instead of proportion active during accrual",
      "actions_required": [
        "accrue_fees",
        "setYieldCut",
        "claim"
      ],
      "scope": "cross_function",
      "halmos_directives": [
        "--loop 3"
      ]
    },
    {
      "category": "conservation",
      "name": "yield_cut_retroactive_preservation",
      "solidity_expr": "totalClaimedByProtocol + totalClaimedByLPs == totalFeesAccrued",
      "quantities_involved": [
        "totalFeesAccrued",
        "totalClaimedByProtocol",
        "totalClaimedByLPs",
        "yieldCut"
      ],
      "violation_pattern": "changing yieldCut mid-period retroactively applies new split to old fees; breaks proportional conservation of LP vs protocol entitlements",
      "actions_required": [
        "swap_generate_fees",
        "setYieldCut",
        "claimFees"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--invariant-depth 3"
      ]
    }
  ],
  "confidence": 0.75,
  "validation": {
    "refuted": true,
    "reason": "The first invariant's solidity expression 'accumulatedFees_before * newYieldCut == accumulatedFees_after * oldYieldCut' is mathematically nonsensical (comparing cross-products of fees and rates that should never be equal) and doesn't capture the actual bug which is that unclaimed fees get distribute"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant's solidity expression 'accumulatedFees_before * newYieldCut == accumulatedFees_after * oldYieldCut' is mathematically nonsensical (comparing cross-products of fees and rates that should never be equal) and doesn't capture the actual bug which is that unclaimed fees get distribute*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 4. 🔴 REFUTED — [M] Withdrawal from NFTs can be temporarily blocked

- Corpus: `2024-02-althea-liquid-infrastructure` (source: c4)
- Body: **Mitigation:** Consider modifying the check [here](<https://github.com/code-423n4/2024-02-althea-liquid-infrastructure/blob/main/liquid-infrastructure/contracts/LiquidInfrastructureERC20.sol#L382>) to:

```diff
+       if (nextWithdrawal >= ManagedNFTs.length) {
            nextWithdrawal = 0;
            emit WithdrawalFinished();
        }
```

**Extracted invariant:**

```json
{
  "extractable": "LIVENESS",
  "driver_shape": "none",
  "resistant_reason": "requires_temporal",
  "structural_invariants": [],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariants are extractable and categorizes this as pure liveness, but the bug is actually about a specific boundary condition (nextWithdrawal >= vs >) that violates the structural invariant that nextWithdrawal should always be reset to 0 when it reaches ManagedNFT"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariants are extractable and categorizes this as pure liveness, but the bug is actually about a specific boundary condition (nextWithdrawal >= vs >) that violates the structural invariant that nextWithdrawal should always be reset to 0 when it reaches ManagedNFT*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 5. ✅ CLEAN — [M] Remove Liquidity has missing reserve1 DUST check, which can make reserve1 to be less than DUST

- Corpus: `2024-01-salty` (source: c4)
- Body: **Mechanism:** The documentation states the following reason for the DUST check:

```solidity
// Make sure that removing liquidity doesn't drive either of the reserves below DUST.
// This is to ensure that ratios remain relatively constant even after a maximum withdrawal.
```

So, if the `reserve1` goes below the DUST amount, then it can imbalance the ratios. Also, once a pool has been established...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "monotonicity",
      "name": "reserve_above_dust_floor",
      "solidity_expr": "reserve0 >= DUST && reserve1 >= DUST",
      "quantities_involved": [
        "reserve0",
        "reserve1",
        "DUST"
      ],
      "violation_pattern": "removeLiquidity checks only reserve0 twice due to typo, allowing reserve1 to fall below DUST threshold and break swap ratio assumptions",
      "actions_required": [
        "removeLiquidity"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "oracle_sanity",
      "name": "reserve_ratio_bounded",
      "solidity_expr": "reserve0 >= DUST && reserve1 >= DUST",
      "quantities_involved": [
        "reserve0",
        "reserve1",
        "DUST"
      ],
      "violation_pattern": "reserve1 below DUST causes ratio imbalance and subsequent swap operations to revert",
      "actions_required": [
        "removeLiquidity",
        "swap"
      ],
      "scope": "contract_invariant",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": false,
    "reason": "The extracted invariants correctly capture that the bug allows reserve1 to fall below DUST due to a typo that checks reserve0 twice, and both invariants accurately describe the postcondition violation (reserve1 < DUST after removeLiquidity) and the downstream consequence (swap operations breaking), "
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *The extracted invariants correctly capture that the bug allows reserve1 to fall below DUST due to a typo that checks reserve0 twice, and both invariants accurately describe the postcondition violation (reserve1 < DUST after removeLiquidity) and the downstream consequence (swap operations breaking), *

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 6. 🔴 REFUTED — [M] Zeta Supply Inflation on Deploy Fungible Gas Coin

- Corpus: `2023-11-zetachain` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "deploy_no_supply_inflation",
      "solidity_expr": "totalSupply_after == totalSupply_before",
      "quantities_involved": [
        "totalSupply"
      ],
      "violation_pattern": "deployFungibleGasCoin mints tokens without accounting, inflating total supply beyond tracked amount",
      "actions_required": [
        "deployFungibleGasCoin"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "no_overflow",
      "name": "supply_stays_in_bounds",
      "solidity_expr": "totalSupply_after <= type(uint256).max",
      "quantities_involved": [
        "totalSupply"
      ],
      "violation_pattern": "uncontrolled minting during deploy can push supply past uint256 max or break tracked invariants",
      "actions_required": [
        "deployFungibleGasCoin"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariant 'totalSupply_after == totalSupply_before' would hold even when the bug fires if the totalSupply variable is correctly updated during minting, making this the wrong invariant\u2014the actual bug is likely that tokens are minted to addresses without corresponding tracked supply increase, or m"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant 'totalSupply_after == totalSupply_before' would hold even when the bug fires if the totalSupply variable is correctly updated during minting, making this the wrong invariant—the actual bug is likely that tokens are minted to addresses without corresponding tracked supply increase, or m*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 7. ✅ CLEAN — [M] `PartyGovernance.sol#accept` - `passThresholdBps` isn't cached for each proposal which can lead to problems if changed through another proposal

- Corpus: `2023-10-party` (source: c4)
- Body: **Mitigation:** We recommend caching `passThresholdBps` in a similar way as `totalVotingPower` is cached for proposals.

**[0xble (Party) confirmed](https://github.com/code-423n4/2023-10-party-findings/issues/295#issuecomment-1821512555)**

***

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "monotonicity",
      "name": "proposal_threshold_immutable_after_creation",
      "solidity_expr": "proposal_threshold_at_accept == proposal_threshold_at_creation",
      "quantities_involved": [
        "passThresholdBps",
        "proposal.passThresholdBps",
        "proposal.createdTime"
      ],
      "violation_pattern": "accept() reads live passThresholdBps instead of snapshot; concurrent proposal changing passThresholdBps retroactively alters pass criteria for in-flight proposals",
      "actions_required": [
        "propose_A",
        "propose_B_changes_threshold",
        "execute_B",
        "accept_A"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 3"
      ]
    },
    {
      "category": "authorization",
      "name": "proposal_pass_criteria_stable",
      "solidity_expr": "votes >= (totalVotingPower_snapshot * passThresholdBps_snapshot) / 10000",
      "quantities_involved": [
        "votes",
        "totalVotingPower",
        "passThresholdBps"
      ],
      "violation_pattern": "accept evaluates proposal against current passThresholdBps not snapshot; threshold mutation between propose and accept changes pass conditions retroactively",
      "actions_required": [
        "propose",
        "vote",
        "change_threshold_via_governance",
        "accept"
      ],
      "scope": "cross_function",
      "halmos_directives": [
        "--loop 3"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": false,
    "reason": "Both invariants correctly capture that the bug violates the property that a proposal's pass threshold should remain constant from creation to acceptance, which is indeed what the bug allows by reading live passThresholdBps instead of a cached snapshot."
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *Both invariants correctly capture that the bug violates the property that a proposal's pass threshold should remain constant from creation to acceptance, which is indeed what the bug allows by reading live passThresholdBps instead of a cached snapshot.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 8. 🔴 REFUTED — [M] Does not check if `to_chain` and `to_handler` is whitelisted in `cross_chain_erc20_settlement`

- Corpus: `2024-08-chakra` (source: c4)
- Body: **Mechanism:** The handler does not prevent tokens from being sent to incorrect chains and handlers. If a message is sent to an incorrect handler, the failure cannot be handled through `receive_cross_chain_callback`.

**Mitigation:** ```diff
function cross_chain_erc20_settlement(
    string memory to_chain,
    uint256 to_handler,
    uint256 to_token,
    uint256 to,
    uint256 amount
) external...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "destination_handler_whitelisted",
      "solidity_expr": "is_valid_handler(to_chain, to_handler) == true",
      "quantities_involved": [
        "to_chain",
        "to_handler",
        "is_valid_handler"
      ],
      "violation_pattern": "cross_chain_erc20_settlement accepts arbitrary destination chain and handler addresses without validating against whitelist, causing tokens to be sent to invalid endpoints where they cannot be recovered",
      "actions_required": [
        "cross_chain_erc20_settlement"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.9,
  "validation": {
    "refuted": true,
    "reason": "The invariant is marked as 'function_postcondition' but expresses a precondition that should be checked before the function executes, and the bug is about missing input validation (a precondition check), not a postcondition that must hold after execution."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant is marked as 'function_postcondition' but expresses a precondition that should be checked before the function executes, and the bug is about missing input validation (a precondition check), not a postcondition that must hold after execution.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 9. 🔴 REFUTED — [M] Depositors could lose all their deposited tokens (including the hTokens) if their address is blacklisted in one of all the deposited underlyingTokens

- Corpus: `2023-09-maia` (source: c4)
- Body: **Mitigation:** When redeeming the failed deposits, the easiest and most straightforward solution is to allow the depositor to pass an address where it would like to receive all the deposited tokens.

```solidity
- function redeemDeposit(uint32 _depositNonce) external override lock {
+ function redeemDeposit(uint32 _depositNonce, address _receiver) external override lock {  
        ...

        
...

**Extracted invariant:**

```json
{
  "extractable": "LIVENESS",
  "driver_shape": "none",
  "resistant_reason": "requires_external_oracle",
  "structural_invariants": [],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariants exist and requires an external oracle, but the bug actually violates a clear structural invariant: funds must be transferable to the owner, which can be checked by verifying that the receiver address parameter exists and is distinct from msg.sender, mak"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariants exist and requires an external oracle, but the bug actually violates a clear structural invariant: funds must be transferable to the owner, which can be checked by verifying that the receiver address parameter exists and is distinct from msg.sender, mak*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 10. 🔴 REFUTED — [M] Invalid handling of flash loan fees in `PositionAction::onCreditFlashLoan`, forcing it to always revert

- Corpus: `2024-10-loopfi` (source: c4)
- Body: **Mitigation:** ```diff
function onCreditFlashLoan(
    address /*initiator*/,
    uint256 /*amount*/,
   uint256 fee,
    bytes calldata data
) external returns (bytes32) {
    ...

    // sub collateral and debt
    ICDPVault(leverParams.vault).modifyCollateralAndDebt(
        leverParams.position,
        address(this),
        address(this),
        0,
-       -toInt256(subDebt)
+       -toInt...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "solvency",
      "name": "flash_loan_repayment_covers_fee",
      "solidity_expr": "debt_reduction + fee_retained >= flash_loan_amount + flash_loan_fee",
      "quantities_involved": [
        "debt",
        "fee",
        "flash_loan_amount"
      ],
      "violation_pattern": "modifyCollateralAndDebt reduces debt by full subDebt without accounting for flash loan fee; callback cannot repay lender because fee amount is missing",
      "actions_required": [
        "onCreditFlashLoan"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "debt_reduction_excludes_fee",
      "solidity_expr": "debt_after == debt_before - (flash_loan_amount + flash_loan_fee) + flash_loan_fee",
      "quantities_involved": [
        "debt_before",
        "debt_after",
        "flash_loan_fee"
      ],
      "violation_pattern": "debt is reduced by full amount including fee, leaving contract short by fee amount when repaying flash loan",
      "actions_required": [
        "onCreditFlashLoan"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The invariants describe accounting relationships but miss the actual bug: the function always reverts because it lacks sufficient balance to repay the flash loan (debt is reduced by the full amount but the contract needs to retain the fee to repay the lender), so the invariant should be about revert"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariants describe accounting relationships but miss the actual bug: the function always reverts because it lacks sufficient balance to repay the flash loan (debt is reduced by the full amount but the contract needs to retain the fee to repay the lender), so the invariant should be about revert*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 11. 🔴 REFUTED — [H] Arbitrary tokens and data can be bridged to `GnosisTargetDispenserL2` to manipulate staking incentives

- Corpus: `2024-05-olas` (source: c4)
- Body: **Mechanism:** An attacker can bridge any tokens to the `GnosisTargetDispenserL2` contract on L2 with fake data for staking incentives. If the contract holds any withheld funds, these funds can be redistributed to arbitrary targets as long as they pass the [checks](https://github.com/code-423n4/2024-05-olas/blob/3ce502ec8b475885b90668e617f3983cea3ae29f/tokenomics/contracts/staking/DefaultTargetDis...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "bridged_data_from_authorized_source",
      "solidity_expr": "msg.sender == authorizedBridge && messageSender == authorizedL1Dispenser",
      "quantities_involved": [
        "msg.sender",
        "messageSender",
        "authorizedBridge",
        "authorizedL1Dispenser"
      ],
      "violation_pattern": "onTokenBridged callback accepts arbitrary caller and data without validating the L1 source; attacker bridges tokens with fake staking incentive payloads",
      "actions_required": [
        "onTokenBridged"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "staking_target_authorized_by_l1",
      "solidity_expr": "authorizedTargets[stakingTarget] == true",
      "quantities_involved": [
        "stakingTarget",
        "authorizedTargets"
      ],
      "violation_pattern": "arbitrary target addresses in bridged data can receive withheld funds or queued amounts without L1 authorization",
      "actions_required": [
        "onTokenBridged",
        "_processData"
      ],
      "scope": "cross_function",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The first invariant assumes existence of 'authorizedBridge', 'authorizedL1Dispenser', and 'messageSender' variables that are not mentioned in the bug report, and the bug explicitly states that 'Omnibridge contracts do not seem to provide a way to access the original sender's address on L1', making t"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant assumes existence of 'authorizedBridge', 'authorizedL1Dispenser', and 'messageSender' variables that are not mentioned in the bug report, and the bug explicitly states that 'Omnibridge contracts do not seem to provide a way to access the original sender's address on L1', making t*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 12. 🔴 REFUTED — [M] Signature replay

- Corpus: `2022-01-insure` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "replay_protection",
      "name": "signature_consumed_at_most_once",
      "solidity_expr": "usedSignatures[digest] == true",
      "quantities_involved": [
        "usedSignatures",
        "digest",
        "keccak256(message)"
      ],
      "violation_pattern": "signature verification lacks replay guard; same (v,r,s) tuple can be re-submitted multiple times",
      "actions_required": [
        "submit_signature",
        "submit_signature_replay"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 3"
      ]
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The invariant states `usedSignatures[digest] == true` which would mean signatures ARE marked as used (the correct state), but a signature replay bug occurs when this tracking is MISSING or BYPASSED, so the invariant as written would actually HOLD during the bug rather than being violated."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant states `usedSignatures[digest] == true` which would mean signatures ARE marked as used (the correct state), but a signature replay bug occurs when this tracking is MISSING or BYPASSED, so the invariant as written would actually HOLD during the bug rather than being violated.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 13. 🔴 REFUTED — [H] `IndexTemplate.sol` Wrong implementation allows lp of the index pool to resume a locked `PayingOut` pool and escape the responsibility for the compensation

- Corpus: `2022-01-insure` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "locked_pool_cannot_resume",
      "solidity_expr": "pool_status == PayingOut implies pool_status_after == PayingOut",
      "quantities_involved": [
        "pool_status",
        "locked",
        "paused"
      ],
      "violation_pattern": "resume() bypasses PayingOut lock check allowing LP to unlock pool before compensation completes",
      "actions_required": [
        "lock_pool_for_payout",
        "resume"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--invariant-depth 2"
      ]
    },
    {
      "category": "monotonicity",
      "name": "payout_obligation_monotonic",
      "solidity_expr": "pool_status == PayingOut implies compensation_debt_after >= compensation_debt_before",
      "quantities_involved": [
        "compensation_debt",
        "pool_status"
      ],
      "violation_pattern": "resuming from PayingOut status allows LP to withdraw before paying full compensation debt",
      "actions_required": [
        "trigger_payout",
        "resume",
        "withdraw"
      ],
      "scope": "cross_function",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'pool_status_after == PayingOut' is trivially satisfied even when the bug fires because resume() does not check PayingOut status but likely changes the status from PayingOut to something else, meaning the invariant describes the intended behavior rather than what actually gets vi"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'pool_status_after == PayingOut' is trivially satisfied even when the bug fires because resume() does not check PayingOut status but likely changes the status from PayingOut to something else, meaning the invariant describes the intended behavior rather than what actually gets vi*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 14. 🔴 REFUTED — [H] Attacker can drain all ETH from `AuctionDemo` when `block.timestamp == auctionEndTime`

- Corpus: `2023-10-nextgen` (source: c4)
- Body: **Mechanism:** Attacker can “win“ an NFT from an auction and steal all ETH deposited for other auctions that are running at the time of the attack.

Condition that enables the attack is that `minter.getAuctionEndTime(_tokenid) == block.timestamp` for some block and for some `_tokenid`.

Let’s assume that:

1. `minter.getAuctionEndTime(_tokenid) % 12` is a uniformly distributed random variable (all...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "ordering",
      "name": "state_cleared_before_refund",
      "solidity_expr": "auctionStatus[tokenId][bidIndex] == false",
      "quantities_involved": [
        "auctionStatus",
        "address(this).balance"
      ],
      "violation_pattern": "claimAuction sends refunds in loop without clearing auction status first; attacker re-enters via fallback and drains all contract ETH",
      "actions_required": [
        "claimAuction",
        "fallback_reenter"
      ],
      "scope": "function_postcondition",
      "halmos_directives": [
        "--loop 4"
      ]
    },
    {
      "category": "authorization",
      "name": "claim_only_after_auction_end",
      "solidity_expr": "block.timestamp > auctionEndTime",
      "quantities_involved": [
        "block.timestamp",
        "auctionEndTime"
      ],
      "violation_pattern": "boundary condition allows claim at exact endTime; attacker can exploit >= comparison to trigger refund phase prematurely",
      "actions_required": [
        "claimAuction"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "balance_covers_single_auction_refunds",
      "solidity_expr": "address(vault).balance >= sum_of_bids_for_tokenId",
      "quantities_involved": [
        "address(this).balance",
        "auctionBids"
      ],
      "violation_pattern": "attacker drains ETH from parallel auctions by re-entering during refund loop when boundary condition is met",
      "actions_required": [
        "claimAuction",
        "fallback_reenter"
      ],
      "scope": "function_postcondition",
      "halmos_directives": [
        "--loop 4"
      ]
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The invariant 'state_cleared_before_refund' checks status after the function completes (postcondition), but the bug requires checking that status is cleared BEFORE each refund is sent (mid-execution ordering), meaning the invariant could hold true even when the reentrancy bug fires since status migh"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant 'state_cleared_before_refund' checks status after the function completes (postcondition), but the bug requires checking that status is cleared BEFORE each refund is sent (mid-execution ordering), meaning the invariant could hold true even when the reentrancy bug fires since status migh*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 15. 🔴 REFUTED — [H] User can evade `liquidation` by depositing the minimum of tokens and gain time to not be liquidated

- Corpus: `2024-01-salty` (source: c4)
- Body: **Mitigation:** Consider modifying the [liquidation](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/stable/CollateralAndLiquidity.sol#L154) function as follows:

<details>

```diff
	function liquidateUser( address wallet ) external nonReentrant
		{
		require( wallet != msg.sender, "Cannot liquidate self" );

		// First, make sure that the user's colla...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "liquidation_not_blockable_by_deposit",
      "solidity_expr": "canUserBeLiquidated(user) implies liquidateUser(user) succeeds",
      "quantities_involved": [
        "userShareForPool",
        "usdsBorrowedByUsers",
        "canUserBeLiquidated"
      ],
      "violation_pattern": "_decreaseUserShare with cooldown=true triggers cooldown period; user deposits minTokens before liquidation to reset cooldown and block liquidation",
      "actions_required": [
        "borrow",
        "price_drop",
        "attacker_deposit_minTokens",
        "liquidateUser"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 4"
      ]
    },
    {
      "category": "ordering",
      "name": "cooldown_not_set_during_liquidation",
      "solidity_expr": "cooldownExpiration_before == cooldownExpiration_after",
      "quantities_involved": [
        "cooldownExpiration",
        "userShareForPool"
      ],
      "violation_pattern": "liquidation calls _decreaseUserShare(cooldown=true) which sets cooldown; subsequent liquidation attempt fails cooldown check despite user still being undercollateralized",
      "actions_required": [
        "liquidateUser"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant is imprecise and likely holds even when the bug fires: the bug allows users to block liquidation by resetting cooldown through deposits, so `liquidateUser(user)` will actually FAIL (not succeed) when `canUserBeLiquidated(user)` is true due to cooldown checks, contradicting the cl"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant is imprecise and likely holds even when the bug fires: the bug allows users to block liquidation by resetting cooldown through deposits, so `liquidateUser(user)` will actually FAIL (not succeed) when `canUserBeLiquidated(user)` is true due to cooldown checks, contradicting the cl*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 16. 🔴 REFUTED — [M] MinShares Slippage Parameters Are Ineffective For Initial Deposit

- Corpus: `2024-01-salty` (source: c4)
- Body: **Mitigation:** Consider using `minAmount0` and `minAmount1` deposited into the AMM. This is how Uniswap V3 implements their slippage parameters.

Alternatively, using the same liquidity formula as Uniswap v2 - $L = sqrt(x \* y)$ will prevent this attack.

**[othernet-global (Salty.IO) confirmed and commented](https://github.com/code-423n4/2024-01-salty-findings/issues/221#issuecomment-1945280386)...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "scripted_trace",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "share_conversion",
      "name": "first_deposit_slippage_protects_shares",
      "solidity_expr": "shares_received >= minShares && amount0_deposited >= minAmount0 && amount1_deposited >= minAmount1",
      "quantities_involved": [
        "shares_received",
        "minShares",
        "amount0_deposited",
        "amount1_deposited"
      ],
      "violation_pattern": "minShares parameter ineffective on first deposit because attacker can manipulate initial share price; victim receives fewer shares than minShares despite parameter being checked",
      "actions_required": [
        "attacker_first_deposit",
        "victim_deposit_with_slippage"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "share_conversion",
      "name": "initial_share_price_bounded",
      "solidity_expr": "totalShares == 0 || (reserves0 * reserves1 > 0 && totalShares * totalShares >= reserves0 * reserves1 / max_inflation_factor)",
      "quantities_involved": [
        "totalShares",
        "reserves0",
        "reserves1"
      ],
      "violation_pattern": "first depositor can create unfavorable share price by depositing imbalanced reserves; subsequent depositors receive inflated or deflated share amounts",
      "actions_required": [
        "first_deposit",
        "second_deposit"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--solver-timeout-assertion 10000"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant's solidity_expr requires ALL conditions (shares >= minShares AND amount0 >= minAmount0 AND amount1 >= minAmount1) to hold, but the bug is specifically that minShares alone is ineffective and the mitigation uses minAmount0/minAmount1 INSTEAD, meaning the invariant conflates the bu"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant's solidity_expr requires ALL conditions (shares >= minShares AND amount0 >= minAmount0 AND amount1 >= minAmount1) to hold, but the bug is specifically that minShares alone is ineffective and the mitigation uses minAmount0/minAmount1 INSTEAD, meaning the invariant conflates the bu*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 17. 🔴 REFUTED — [H] Single plot can be occupied by multiple renters

- Corpus: `2024-07-munchables` (source: c4)
- Body: **Mechanism:** If the amount of landlord's plots is decreased and user's token is inside a plot outside of the new range, the token won't be set as dirty.

This can lead to a situation where a user can stake initially on the first plots but after that move his token to a plot that is in the end of the range. When the plots are decreased, the contract will still think the token is in the first plot...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "plot_occupancy_unique",
      "solidity_expr": "plotOccupied[landlord][plotId].occupied == true implies (forall tokenId2 where tokenId2 != plotOccupied[landlord][plotId].tokenId : toilerState[tokenId2].plotId != plotId || toilerState[tokenId2].landlord != landlord)",
      "quantities_involved": [
        "plotOccupied",
        "toilerState",
        "plotId",
        "tokenId"
      ],
      "violation_pattern": "movePlot updates plotOccupied but fails to sync toilerState.plotId; after landlord decreases plot count, stale toilerState entry allows double-occupancy",
      "actions_required": [
        "stake",
        "movePlot",
        "decreasePlotCount",
        "stake_again"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 4"
      ]
    },
    {
      "category": "conservation",
      "name": "toiler_state_synced_with_plot",
      "solidity_expr": "toilerState[tokenId].plotId == actualPlotId && plotOccupied[landlord][actualPlotId].tokenId == tokenId",
      "quantities_involved": [
        "toilerState[tokenId].plotId",
        "plotOccupied[landlord][plotId].tokenId"
      ],
      "violation_pattern": "toilerState.plotId not updated during movePlot creates desync between token location record and plot occupancy map",
      "actions_required": [
        "movePlot"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'plot_occupancy_unique' would still hold even when the bug fires because the stale toilerState entry has an old plotId value that doesn't match the actual plot being double-occupied, so the universal quantifier would not detect the conflict."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'plot_occupancy_unique' would still hold even when the bug fires because the stale toilerState entry has an old plotId value that doesn't match the actual plot being double-occupied, so the universal quantifier would not detect the conflict.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 18. 🔴 REFUTED — [M] Gas used mismatch in failed contract calls can lead to wrong gas deductions

- Corpus: `2024-11-nibiru` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "gas_accounting_matches_actual_consumption",
      "solidity_expr": "gas_deducted == gas_consumed",
      "quantities_involved": [
        "gasUsed",
        "gasDeducted",
        "gasRemaining"
      ],
      "violation_pattern": "failed contract calls return incorrect gas usage values leading to mismatch between recorded gas deductions and actual gas consumed",
      "actions_required": [
        "contract_call"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "gas_pool_balance_tracks_obligations",
      "solidity_expr": "gas_pool >= sum_of_gas_obligations",
      "quantities_involved": [
        "gasPool",
        "totalGasDeducted"
      ],
      "violation_pattern": "incorrect gas deduction on failed calls causes gas pool accounting to diverge from actual gas obligations",
      "actions_required": [
        "contract_call"
      ],
      "scope": "contract_invariant",
      "halmos_directives": []
    }
  ],
  "confidence": 0.8,
  "validation": {
    "refuted": true,
    "reason": "The invariant describes abstract gas accounting relationships but the bug is about a mismatch in gas values returned from failed calls, and these extracted invariants could actually hold even when the bug fires if the system never checks or enforces these relationships, making them non-falsifiable w"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant describes abstract gas accounting relationships but the bug is about a mismatch in gas values returned from failed calls, and these extracted invariants could actually hold even when the bug fires if the system never checks or enforces these relationships, making them non-falsifiable w*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 19. 🔴 REFUTED — [H] backdoor in `withdrawRedundant`

- Corpus: `2022-01-insure` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "TRUST",
  "driver_shape": "none",
  "resistant_reason": "documented_trust_assumption",
  "structural_invariants": [],
  "confidence": 0.95,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariant exists and categorizes this as a trust assumption, but a backdoor in withdrawRedundant violates an access control invariant (e.g., 'only authorized parties can withdraw funds') which is a checkable structural property, not merely a trust assumption."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariant exists and categorizes this as a trust assumption, but a backdoor in withdrawRedundant violates an access control invariant (e.g., 'only authorized parties can withdraw funds') which is a checkable structural property, not merely a trust assumption.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 20. 🔴 REFUTED — [M] `swap_2` implementation will randomly revert due to improper check, root cause for failed test `ethers_suite_uniswap_orchestrated_uniswap_two`

- Corpus: `2024-08-superposition` (source: c4)
- Body: **Mitigation:** Consider removing/relaxing the strict equality check.

**[af-afk (Superposition) confirmed](https://github.com/code-423n4/2024-08-superposition-findings/issues/31#event-14300539250)**

**[0xsomeone (judge) commented](https://github.com/code-423n4/2024-08-superposition-findings/issues/30#issuecomment-2369650553):**
 > The submission and its duplicates have correctly identified that ...

**Extracted invariant:**

```json
{
  "extractable": "LIVENESS",
  "driver_shape": "none",
  "resistant_reason": "requires_fairness",
  "structural_invariants": [],
  "confidence": 0.9,
  "validation": {
    "refuted": true,
    "reason": "The extracted invariant classifies this as a liveness property requiring fairness analysis, but the bug is actually a safety violation where a strict equality check causes deterministic reverts on valid transactions, making it verifiable as a functional correctness property without fairness consider"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extracted invariant classifies this as a liveness property requiring fairness analysis, but the bug is actually a safety violation where a strict equality check causes deterministic reverts on valid transactions, making it verifiable as a functional correctness property without fairness consider*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 21. 🔴 REFUTED — [H] Neglect of exceptional redistribution amounts in `withdraw_helper` function

- Corpus: `2024-01-opus` (source: c4)
- Body: The `withdraw_helper` function in the `shrine` contract handles withdrawal logic for both the `withdraw` and `seize` functions. It is responsible for updating trove balances, total yang balances, and charging interest for the trove via the `charge` function. However, there is an oversight in the current implementation:

```cairo
fn withdraw_helper(ref self: ContractState, yang: ContractAddress, tr...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "scripted_trace",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "exceptional_redistribution_preserved",
      "solidity_expr": "deposits[yang][trove] >= deposits_before[yang][trove] - withdrawn_amount",
      "quantities_involved": [
        "deposits",
        "withdrawn_amount",
        "exceptional_redistribution"
      ],
      "violation_pattern": "withdraw_helper computes new_trove_balance before charge() call; charge() adds exceptional redistribution to deposits; withdraw_helper overwrites deposits with stale new_trove_balance, erasing the redistribution",
      "actions_required": [
        "charge",
        "withdraw"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "ordering",
      "name": "charge_effect_observed_in_withdrawal",
      "solidity_expr": "deposits_after_charge[yang][trove] == deposits_written[yang][trove]",
      "quantities_involved": [
        "deposits",
        "yang_total",
        "charge"
      ],
      "violation_pattern": "state read (trove_balance) happens before charge() side-effects; state write happens after charge() but uses pre-charge value, creating read-execute-write race",
      "actions_required": [
        "charge",
        "withdraw"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "yang_total_tracks_all_deposits",
      "solidity_expr": "yang_total[yang] == sum_over_troves(deposits[yang][trove])",
      "quantities_involved": [
        "yang_total",
        "deposits"
      ],
      "violation_pattern": "exceptional redistribution increases individual trove deposits but yang_total is written with pre-charge value, breaking invariant that total equals sum of parts",
      "actions_required": [
        "charge",
        "withdraw"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 4"
      ]
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'deposits[yang][trove] >= deposits_before[yang][trove] - withdrawn_amount' can hold even when the bug fires because the bug causes deposits to be *lower* than they should be (by erasing exceptional redistribution), which would make the actual value *less than* the right-hand side"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'deposits[yang][trove] >= deposits_before[yang][trove] - withdrawn_amount' can hold even when the bug fires because the bug causes deposits to be *lower* than they should be (by erasing exceptional redistribution), which would make the actual value *less than* the right-hand side*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 22. 🔴 REFUTED — [M] Missing disapproval check in `LockManager.sol::approveUSDPrice` allows simultaneous approval and disapproval of a price proposal

- Corpus: `2024-05-munchables` (source: c4)
- Body: **Mechanism:** Due to the missing disapproval check, a price feed can both disapprove and subsequently approve a newly proposed price. Price feeds are intended to vote either for approval or disapproval, not both. Hence, this can be considered an unintended functionality.

**Mitigation:** Add a check to see if the price feed has already disapproved the price proposal. If so, revert with a custom e...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "mutually_exclusive_votes",
      "solidity_expr": "!(approvals[voter] == proposalId && disapprovals[voter] == proposalId)",
      "quantities_involved": [
        "approvals[voter]",
        "disapprovals[voter]",
        "proposalId"
      ],
      "violation_pattern": "approveUSDPrice lacks disapproval check, allowing voter to register both approval and disapproval for same proposal",
      "actions_required": [
        "disapproveUSDPrice",
        "approveUSDPrice"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--invariant-depth 3"
      ]
    },
    {
      "category": "monotonicity",
      "name": "vote_finality",
      "solidity_expr": "(disapprovals[voter] == proposalId) ==> (approvals[voter] != proposalId)",
      "quantities_involved": [
        "approvals[voter]",
        "disapprovals[voter]",
        "proposalId"
      ],
      "violation_pattern": "voter can change disapproval to approval, violating vote immutability assumption in quorum counting",
      "actions_required": [
        "disapproveUSDPrice",
        "approveUSDPrice"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--invariant-depth 3"
      ]
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The invariant `!(approvals[voter] == proposalId && disapprovals[voter] == proposalId)` can HOLD even when the bug fires, because the bug allows sequential voting (disapprove then approve), which would result in `approvals[voter] == proposalId` and `disapprovals[voter] == proposalId` being both true "
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant `!(approvals[voter] == proposalId && disapprovals[voter] == proposalId)` can HOLD even when the bug fires, because the bug allows sequential voting (disapprove then approve), which would result in `approvals[voter] == proposalId` and `disapprovals[voter] == proposalId` being both true *

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 23. 🔴 REFUTED — [M] Creation of token whitelisting proposals can be DOS'd

- Corpus: `2024-01-salty` (source: c4)
- Body: **Mechanism:** Malicious users can clog the whitelisting queue with fake token proposals, blocking the addition of genuine tokens and DOSing core functionality of the protocol.
This can restrict the ability of the protocol to operate and it's popularity with users.
Although a user can only create one proposal per address at a time; a coordinated group of just five could block the functionality ind...

**Extracted invariant:**

```json
{
  "extractable": "LIVENESS",
  "driver_shape": "none",
  "resistant_reason": "requires_fairness",
  "structural_invariants": [],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The extracted invariant claims 'LIVENESS' but this is a resource exhaustion/DOS bug that could be expressed as a safety property about bounded queue occupancy or proposal limits per entity, not inherently requiring fairness assumptions for verification."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extracted invariant claims 'LIVENESS' but this is a resource exhaustion/DOS bug that could be expressed as a safety property about bounded queue occupancy or proposal limits per entity, not inherently requiring fairness assumptions for verification.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 24. 🔴 REFUTED — [M] `LiquidateWithReplacement` does not charge swap fees on the borrower

- Corpus: `2024-06-size` (source: c4)
- Body: **Mitigation:** Also charge swap fees during `executeLiquidateWithReplacement`.

**[aviggiano (Size) acknowledged and commented](https://github.com/code-423n4/2024-06-size-findings/issues/53#issuecomment-2210760287):**
 > Feedback from the team:
> 
> - Technically valid observation.
> - Whether we fix it or not is a product decision.
> - Technically this is a valid one since it is a credit for cas...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "liquidate_replacement_charges_swap_fee",
      "solidity_expr": "borrower_balance_before - borrower_balance_after >= debt_amount + swap_fee",
      "quantities_involved": [
        "borrower_balance",
        "debt_amount",
        "swap_fee",
        "protocol_fee_accumulated"
      ],
      "violation_pattern": "liquidateWithReplacement executes credit-for-cash operation without charging swap fee to borrower, inconsistent with standard credit sell orders",
      "actions_required": [
        "liquidateWithReplacement"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "swap_fee_consistency_across_credit_operations",
      "solidity_expr": "is_credit_sell_operation implies swap_fee_charged == true",
      "quantities_involved": [
        "swap_fee_charged",
        "operation_type"
      ],
      "violation_pattern": "liquidateWithReplacement bypasses swap fee that would be charged if same credit-sell operation executed via standard limit order fill",
      "actions_required": [
        "liquidateWithReplacement"
      ],
      "scope": "cross_function",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariant 'borrower_balance_before - borrower_balance_after >= debt_amount + swap_fee' could still hold even when the bug fires because the borrower may pay debt_amount plus other fees/costs without the swap_fee being explicitly charged, making this an unreliable detector of the specific swap fe"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant 'borrower_balance_before - borrower_balance_after >= debt_amount + swap_fee' could still hold even when the bug fires because the borrower may pay debt_amount plus other fees/costs without the swap_fee being explicitly charged, making this an unreliable detector of the specific swap fe*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 25. 🔴 REFUTED — [M] `UpdateExpirattionPeriod()` cannot be executed when the `newExpirationPeriod` is less than `currentExpirationPeriod`

- Corpus: `2024-10-kleidi` (source: c4)
- Body: **Mitigation:** ```solidity
 function _afterCall(bytes32 id) private {
       //no need to check
        timestamps[id] = _DONE_TIMESTAMP;
    }
```

**[ElliotFriedman (Kleidi) confirmed, but disagreed with severity and commented](https://github.com/code-423n4/2024-10-kleidi-findings/issues/9#issuecomment-2445088158):**
 > Seems like this is a valid issue, but it's valid only if you execute the pr...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "scripted_trace",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "ordering",
      "name": "parameter_update_before_validation",
      "solidity_expr": "expirationPeriod_at_schedule == expirationPeriod_at_execute",
      "quantities_involved": [
        "expirationPeriod",
        "timestamps[id]",
        "block.timestamp"
      ],
      "violation_pattern": "updateExpirationPeriod proposal changes expirationPeriod state before the proposal itself executes; execute() then validates against the new (shorter) period and reverts",
      "actions_required": [
        "schedule_updateExpirationPeriod",
        "warp_past_minDelay",
        "execute_updateExpirationPeriod"
      ],
      "scope": "cross_function",
      "halmos_directives": [
        "--solver-timeout-assertion 10000"
      ]
    },
    {
      "category": "ordering",
      "name": "expiration_check_uses_original_period",
      "solidity_expr": "block.timestamp <= timestamps[id] + expirationPeriod_original",
      "quantities_involved": [
        "block.timestamp",
        "timestamps[id]",
        "expirationPeriod"
      ],
      "violation_pattern": "execute() validates timestamp + expirationPeriod but expirationPeriod was already mutated by the proposal being executed; creating circular dependency",
      "actions_required": [
        "schedule",
        "update_expirationPeriod",
        "execute"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariant 'expirationPeriod_at_schedule == expirationPeriod_at_execute' would actually HOLD when the bug fires (both would be the new shorter period), whereas the actual bug violation is 'block.timestamp > timestamps[id] + newExpirationPeriod' when 'block.timestamp <= timestamps[id] + oldExpirat"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant 'expirationPeriod_at_schedule == expirationPeriod_at_execute' would actually HOLD when the bug fires (both would be the new shorter period), whereas the actual bug violation is 'block.timestamp > timestamps[id] + newExpirationPeriod' when 'block.timestamp <= timestamps[id] + oldExpirat*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 26. 🔴 REFUTED — [M] Exiting a farm on mainnet assumes a peg of `1:1`  when swapping stETH for ETH

- Corpus: `2024-02-wise-lending` (source: c4)
- Body: **Mitigation:** The recommendation would be to implement a mitigation similar to the one implemented on the referenced issues.
Basically, fetch the current price of `stETH` from a Chainlink Oracle and multiply the `minOutAmount` by the current price of `stETH`. In this way, the `minOutAmount` that is sent to the Curves exchange will now be within the correct limits based on the current price of st...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "oracle_sanity",
      "name": "steth_price_used_for_minout",
      "solidity_expr": "minOutAmount * stethPrice >= expectedAmount * 1e18",
      "quantities_involved": [
        "minOutAmount",
        "stethPrice",
        "expectedAmount"
      ],
      "violation_pattern": "exitFarm hardcodes 1:1 stETH:ETH peg assumption for minOutAmount, ignoring actual stETH price from oracle",
      "actions_required": [
        "exitFarm"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "slippage_check_uses_consistent_pricing",
      "solidity_expr": "ethValueAfter * 1e18 >= ethValueBefore * stethPrice * (1e18 - maxSlippage) / 1e18",
      "quantities_involved": [
        "ethValueAfter",
        "ethValueBefore",
        "stethPrice",
        "maxSlippage"
      ],
      "violation_pattern": "ethValueBefore computed at 1:1 peg while ethValueAfter uses actual swap output; slippage check compares mismatched pricing bases",
      "actions_required": [
        "exitFarm",
        "swap"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariants describe what SHOULD be true after mitigation (using stethPrice correctly), but the actual bug violation is that minOutAmount and ethValueBefore are computed WITHOUT multiplying by stethPrice (assuming 1:1 peg), so these invariants would NOT hold when the bug fires, making them post-f"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariants describe what SHOULD be true after mitigation (using stethPrice correctly), but the actual bug violation is that minOutAmount and ethValueBefore are computed WITHOUT multiplying by stethPrice (assuming 1:1 peg), so these invariants would NOT hold when the bug fires, making them post-f*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 27. 🔴 REFUTED — [H] Weak randomness in PuppyRaffle::selectWinner allows anyone to choose winner

- Corpus: `puppy-raffle` (source: examples)
- Body: `selectWinner` derives randomness from `keccak256(abi.encodePacked(msg.sender, block.timestamp, block.difficulty))`. All inputs are miner/sender-influenced, so the outcome is predictable / griefable. Faithful fix: Chainlink VRF or commit-reveal.

**Extracted invariant:**

```json
{
  "extractable": "EXTERNAL",
  "driver_shape": "none",
  "resistant_reason": "requires_external_oracle",
  "structural_invariants": [],
  "confidence": 0.9,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariant is extractable and requires an external oracle, but the bug actually violates a concrete structural property: the randomness source must not be deterministically computable from publicly available or attacker-controllable inputs, which is a checkable inv"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariant is extractable and requires an external oracle, but the bug actually violates a concrete structural property: the randomness source must not be deterministically computable from publicly available or attacker-controllable inputs, which is a checkable inv*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 28. 🔴 REFUTED — [M] The gauge status wasn't checked before reducing the user's gauge weight.

- Corpus: `2023-12-ethereumcreditguild` (source: c4)
- Body: **Mitigation:** Check if all loans have been closed in `GuildToken#_decrementGaugeWeight()`:

```diff
    function _decrementGaugeWeight(
        address user,
        address gauge,
        uint256 weight
    ) internal override {
        uint256 _lastGaugeLoss = lastGaugeLoss[gauge];
        uint256 _lastGaugeLossApplied = lastGaugeLossApplied[gauge][user];
        require(
            _lastGaug...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "deprecated_gauge_requires_zero_issuance",
      "solidity_expr": "!isDeprecatedGauge(gauge) || issuance == 0",
      "quantities_involved": [
        "isDeprecatedGauge(gauge)",
        "issuance"
      ],
      "violation_pattern": "decrementGaugeWeight allows weight reduction on deprecated gauge before all loans are closed; should enforce zero issuance for deprecated gauges",
      "actions_required": [
        "decrementGaugeWeight"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "ordering",
      "name": "gauge_status_checked_before_weight_change",
      "solidity_expr": "gaugeWeight_after <= gaugeWeight_before",
      "quantities_involved": [
        "getUserGaugeWeight(user, gauge)",
        "isDeprecatedGauge(gauge)",
        "issuance"
      ],
      "violation_pattern": "gauge deprecation status and loan closure state must be validated before allowing weight decrement to prevent premature exit from deprecated gauges",
      "actions_required": [
        "decrementGaugeWeight"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The second invariant 'gauge_status_checked_before_weight_change' with solidity_expr 'gaugeWeight_after <= gaugeWeight_before' would hold even when the bug fires (since decrementGaugeWeight always reduces weight), making it useless for detecting the actual violation which is about allowing decrements"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The second invariant 'gauge_status_checked_before_weight_change' with solidity_expr 'gaugeWeight_after <= gaugeWeight_before' would hold even when the bug fires (since decrementGaugeWeight always reduces weight), making it useless for detecting the actual violation which is about allowing decrements*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 29. 🔴 REFUTED — [M] `checkpoint` function is not called before staking which can cause loss of rewards for already staked services

- Corpus: `2024-05-olas` (source: c4)
- Body: **Mitigation:** Call the `checkpoint` function at the start of `stake` function as follows:

<details>

```solidity
function stake(uint256 serviceId) external {
==>         checkpoint();
        // Check if there available rewards
        if (availableRewards == 0) {
            revert NoRewardsAvailable();
        }

        // Check if the evicted service has not yet unstaked
        ServiceInfo...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "ordering",
      "name": "checkpoint_before_stake",
      "solidity_expr": "last_checkpoint_timestamp == block.timestamp",
      "quantities_involved": [
        "last_checkpoint_timestamp",
        "block.timestamp",
        "availableRewards",
        "accumulatedRewards"
      ],
      "violation_pattern": "stake() executes without calling checkpoint() first; accumulated rewards for existing stakers are not recorded before new service dilutes the pool",
      "actions_required": [
        "stake_service_1",
        "earn_rewards",
        "stake_service_2"
      ],
      "scope": "function_postcondition",
      "halmos_directives": [
        "--loop 4"
      ]
    },
    {
      "category": "conservation",
      "name": "reward_pool_consistency",
      "solidity_expr": "total_allocated_rewards + availableRewards <= total_reward_budget",
      "quantities_involved": [
        "total_allocated_rewards",
        "availableRewards",
        "total_reward_budget"
      ],
      "violation_pattern": "missing checkpoint before stake causes reward accounting mismatch; existing stakers lose their accrued-but-not-checkpointed share",
      "actions_required": [
        "checkpoint",
        "stake"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--invariant-depth 3"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'last_checkpoint_timestamp == block.timestamp' would need to hold at every block after checkpoint is called, but the bug violates it only at the moment stake() is called without checkpoint() - this invariant could hold in non-buggy executions and fail in buggy ones at different t"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'last_checkpoint_timestamp == block.timestamp' would need to hold at every block after checkpoint is called, but the bug violates it only at the moment stake() is called without checkpoint() - this invariant could hold in non-buggy executions and fail in buggy ones at different t*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 30. 🔴 REFUTED — [H] Taiko L1 - Proposer can maliciously cause loss of funds by forcing someone else to pay prover's fee

- Corpus: `2024-03-taiko` (source: c4)
- Body: **Mitigation:** A simple fix to this to ensure the block proposer will always be the msg.sender, as such:

        if (params.coinbase == address(0 || params.coinbase != msg.sender)) {
            params.coinbase = msg.sender;
        }

**[dantaik (Taiko) confirmed and commented](https://github.com/code-423n4/2024-03-taiko-findings/issues/163#issuecomment-2032257802):**
 > This is a valid bug rep...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "coinbase_must_be_proposer",
      "solidity_expr": "params.coinbase == msg.sender",
      "quantities_involved": [
        "params.coinbase",
        "msg.sender"
      ],
      "violation_pattern": "proposer can set arbitrary coinbase address causing fees to be paid by victim rather than proposer",
      "actions_required": [
        "proposeBlock"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.95,
  "validation": {
    "refuted": true,
    "reason": "The invariant states params.coinbase must equal msg.sender as a postcondition, but the bug describes that the proposer can set params.coinbase to an arbitrary address (not msg.sender) which would violate this invariant before any correction is applied; however, the mitigation code shows the fix is t"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant states params.coinbase must equal msg.sender as a postcondition, but the bug describes that the proposer can set params.coinbase to an arbitrary address (not msg.sender) which would violate this invariant before any correction is applied; however, the mitigation code shows the fix is t*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 31. 🔴 REFUTED — [M] Users can deflate other markets Guild holders rewards by staking less priced token

- Corpus: `2023-12-ethereumcreditguild` (source: c4)
- Body: **Mitigation:** To prevent manipulation, add a check in the `stake()` function to ensure that the passed term is from the same market as the `SurplusGuildMinter`.

```diff
function stake(address term, uint256 amount) external whenNotPaused {
+   require(LendingTerm(term).getReferences().creditToken == credit, "SurplusGuildMinter: term from wrong market!");

    // apply pending rewards
    (uint25...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "term_market_matches_minter_market",
      "solidity_expr": "term.creditToken() == minter.credit()",
      "quantities_involved": [
        "term.creditToken",
        "minter.credit"
      ],
      "violation_pattern": "stake() accepts arbitrary term address from any market; attacker stakes low-value token from different market to dilute reward share for legitimate stakers in target market",
      "actions_required": [
        "stake"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "rewards_proportional_to_same_market_stakes",
      "solidity_expr": "term_market == credit_market",
      "quantities_involved": [
        "term.getReferences().creditToken",
        "minter.credit"
      ],
      "violation_pattern": "cross-market staking allows attacker to inflate gauge weight with cheap tokens while claiming rewards denominated in expensive market's credit token",
      "actions_required": [
        "stake"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The extracted invariants would NOT be violated when the bug fires because both invariants check equality between term's creditToken and minter's credit, but the bug occurs when a term from a *different* market (with different creditToken) is used, meaning the invariant would correctly evaluate to fa"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extracted invariants would NOT be violated when the bug fires because both invariants check equality between term's creditToken and minter's credit, but the bug occurs when a term from a *different* market (with different creditToken) is used, meaning the invariant would correctly evaluate to fa*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 32. 🔴 REFUTED — [M] Lender of a PAY order lending can grief renter of the payment

- Corpus: `2024-01-renft` (source: c4)
- Body: **Mechanism:** A malicious lender can use this vulnerability to grief a PAY order renter of their payment by having the  `onERC721Received()` or `onERC1155BatchReceived()` callback function revert or not return the magic bytes4 value. They will need to give up the lent out NFT in return which will be stuck in the renter's Safe (and usable for the renter within the limitations of the rental Safe).
...

**Extracted invariant:**

```json
{
  "extractable": "LIVENESS",
  "driver_shape": "none",
  "resistant_reason": "requires_fairness",
  "structural_invariants": [],
  "confidence": 0.9,
  "validation": {
    "refuted": true,
    "reason": "The extracted invariant claims this is a liveness issue requiring fairness, but the bug actually violates a safety property where a malicious callback can permanently block asset reclamation, which is verifiable without fairness assumptions and should be classified as a safety violation with specifi"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extracted invariant claims this is a liveness issue requiring fairness, but the bug actually violates a safety property where a malicious callback can permanently block asset reclamation, which is verifiable without fairness assumptions and should be classified as a safety violation with specifi*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 33. 🔴 REFUTED — [M] Asymmetric calculation of price difference

- Corpus: `2024-03-revert-lend` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "oracle_sanity",
      "name": "symmetric_price_difference",
      "solidity_expr": "abs(priceA - priceB) == abs(priceB - priceA)",
      "quantities_involved": [
        "priceA",
        "priceB",
        "price_difference"
      ],
      "violation_pattern": "price difference computed asymmetrically (e.g., (A-B)/A vs (B-A)/B) yields different bounds depending on ordering, allowing inconsistent deviation checks",
      "actions_required": [
        "price_check"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "oracle_sanity",
      "name": "relative_deviation_bounded",
      "solidity_expr": "abs(priceA * denominator - priceB * denominator) * max_deviation >= abs(priceA - priceB) * denominator * denominator",
      "quantities_involved": [
        "priceA",
        "priceB",
        "max_deviation"
      ],
      "violation_pattern": "asymmetric relative-difference formula ((A-B)/A vs (A-B)/B) creates directional bias where price pair passes check in one order but fails in reverse",
      "actions_required": [
        "oracle_read",
        "price_validation"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'abs(priceA - priceB) == abs(priceB - priceA)' is a mathematical tautology that always holds regardless of whether the bug is present, since absolute value of differences is always symmetric, so it cannot detect the asymmetric calculation bug."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'abs(priceA - priceB) == abs(priceB - priceA)' is a mathematical tautology that always holds regardless of whether the bug is present, since absolute value of differences is always symmetric, so it cannot detect the asymmetric calculation bug.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 34. 🔴 REFUTED — [M] Batched liquidations doesn't distribute bad debt on next batches in the list

- Corpus: `2023-10-badger` (source: c4)
- Body: **Mechanism:** Bad debt is distributed incorrectly.

**Mitigation:** You need to redistribute bad debt after each liquidation in the batch (in case if bad debt occured).

**[Alex the Entreprenerd (Badger) acknowledged and commented](https://github.com/code-423n4/2023-10-badger-findings/issues/36#issuecomment-1818533285):**
 > This is a known finding from Cantina that unfortunately was not added to...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "bad_debt_fully_redistributed_in_batch",
      "solidity_expr": "systemDebt_after == systemDebt_before - totalRepaid + badDebt_redistributed",
      "quantities_involved": [
        "systemDebt",
        "totalRepaid",
        "badDebt"
      ],
      "violation_pattern": "batch liquidation does not redistribute bad debt to subsequent positions in same batch; 3% bad debt skipped per batch",
      "actions_required": [
        "batchLiquidate"
      ],
      "scope": "function_postcondition",
      "halmos_directives": [
        "--loop 4"
      ]
    },
    {
      "category": "ordering",
      "name": "redistribute_bad_debt_before_next_liquidation",
      "solidity_expr": "badDebt_from_previous == 0",
      "quantities_involved": [
        "badDebt",
        "liquidationIndex"
      ],
      "violation_pattern": "bad debt from liquidation[i] must be redistributed before liquidation[i+1] processes; current code defers until batch end",
      "actions_required": [
        "liquidate_position_i",
        "redistribute",
        "liquidate_position_i_plus_1"
      ],
      "scope": "cross_function",
      "halmos_directives": [
        "--loop 4"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'bad_debt_fully_redistributed_in_batch' would still hold even when the bug fires because the bug is about *when* redistribution happens (after each liquidation vs. at batch end), not whether the total system debt accounting is correct at the function's end, making it unable to de"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'bad_debt_fully_redistributed_in_batch' would still hold even when the bug fires because the bug is about *when* redistribution happens (after each liquidation vs. at batch end), not whether the total system debt accounting is correct at the function's end, making it unable to de*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 35. 🔴 REFUTED — [M] Innocent borrower could incur losses caused by a malicious lender

- Corpus: `2024-04-lavarage` (source: c4)
- Body: **Mitigation:** Allow the borrower to pass maximum interest rate, this protects the borrower from any change of the interest rate that occur after they send their TX.

Another suggestion: store the interest rate on position level instead.

**[piske-alex (Lavarage) confirmed and commented](https://github.com/code-423n4/2024-04-lavarage-findings/issues/17#issuecomment-2087769388):**
 > > Another sug...

**Extracted invariant:**

```json
{
  "extractable": "HYPER",
  "driver_shape": "none",
  "resistant_reason": "requires_multi_tx_ordering",
  "structural_invariants": [],
  "confidence": 0.95,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariant exists and marks it as HYPER requiring multi-tx ordering, but the bug actually violates a simple structural property: the interest rate used in a borrow operation should not exceed a user-specified maximum, which is a single-transaction state relationshi"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariant exists and marks it as HYPER requiring multi-tx ordering, but the bug actually violates a simple structural property: the interest rate used in a borrow operation should not exceed a user-specified maximum, which is a single-transaction state relationshi*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 36. ✅ CLEAN — [M] Auction payout goes to `AuctionDemo` contract owner, not the token owner

- Corpus: `2023-10-nextgen` (source: c4)
- Body: **Mechanism:** Any auction executed through `AuctionDemo` will have proceeds sent to the `AuctionDemo` contract owner, not the token owner. The token owner is left without auction proceeds.

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "auction_payout_to_token_owner",
      "solidity_expr": "payout_recipient == token_owner",
      "quantities_involved": [
        "payout_recipient",
        "token_owner",
        "ownerOf(tokenId)"
      ],
      "violation_pattern": "auction proceeds are sent to contract owner instead of the NFT token owner who supplied the auctioned asset",
      "actions_required": [
        "claimAuction"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "token_owner_balance_increases_by_bid",
      "solidity_expr": "token_owner_balance_after >= token_owner_balance_before + winning_bid",
      "quantities_involved": [
        "balanceOf(token_owner)",
        "winning_bid"
      ],
      "violation_pattern": "auction settlement transfers winning bid to wrong recipient; token owner's balance does not increase by auction proceeds",
      "actions_required": [
        "claimAuction"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": false,
    "reason": "Both invariants correctly capture properties violated by the bug: the first checks that payout goes to the token owner (authorization), and the second checks that the token owner's balance increases by the winning bid (conservation), both of which fail when proceeds are misdirected to the contract o"
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *Both invariants correctly capture properties violated by the bug: the first checks that payout goes to the token owner (authorization), and the second checks that the token owner's balance increases by the winning bid (conservation), both of which fail when proceeds are misdirected to the contract o*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 37. 🔴 REFUTED — [M] Value of kerosene can be manipulated to force liquidate users

- Corpus: `2024-04-dyad` (source: c4)
- Body: **Mitigation:** Add a TWAP mechanism to calculate the price of kerosene. The price of kerosene being manipulatable instantaneously is a huge risk. By using a TWAP mechanism, the price of kerosene will be more stable, and users will have more time to react to changes in the price of kerosene.

**Extracted invariant:**

```json
{
  "extractable": "EXTERNAL",
  "driver_shape": "none",
  "resistant_reason": "requires_external_oracle",
  "structural_invariants": [],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The extraction claims no structural invariants can be captured, but the bug clearly violates a temporal property that price changes should be bounded by TWAP smoothing rather than being instantaneously manipulatable, which could be expressed as a structural invariant about price change rates or orac"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The extraction claims no structural invariants can be captured, but the bug clearly violates a temporal property that price changes should be bounded by TWAP smoothing rather than being instantaneously manipulatable, which could be expressed as a structural invariant about price change rates or orac*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 38. 🔴 REFUTED — [M] Incorrect __Essential_init() function is used in TaikoToken making snapshooter devoid of calling snapshot()

- Corpus: `2024-03-taiko` (source: c4)
- Body: **Mitigation:** In the [init()](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/L1/TaikoToken.sol#L25) function, consider using the [\__Essential_init()](https://github.com/code-423n4/2024-03-taiko/blob/f58384f44dbf4c6535264a472322322705133b11/packages/protocol/contracts/common/EssentialContract.sol#L95) function with the owner ...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "snapshooter_role_initialized",
      "solidity_expr": "hasRole(SNAPSHOOTER_ROLE, snapshooter_address) == true",
      "quantities_involved": [
        "snapshooter_address",
        "SNAPSHOOTER_ROLE"
      ],
      "violation_pattern": "init() calls __Essential_init(owner) overload which skips address manager resolution; snapshooter role is never granted",
      "actions_required": [
        "init"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "snapshot_caller_authorized",
      "solidity_expr": "hasRole(SNAPSHOOTER_ROLE, msg.sender) == true",
      "quantities_involved": [
        "msg.sender",
        "SNAPSHOOTER_ROLE"
      ],
      "violation_pattern": "snapshot() requires SNAPSHOOTER_ROLE but init used wrong overload so role was never assigned to snapshooter",
      "actions_required": [
        "init",
        "snapshot"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariants assume a specific snapshooter_address exists and should have the role, but the bug description doesn't specify that a snapshooter address is passed or exists at init time\u2014the issue is that the wrong init overload prevents the address manager from being set up, which would later resolv"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariants assume a specific snapshooter_address exists and should have the role, but the bug description doesn't specify that a snapshooter address is passed or exists at init time—the issue is that the wrong init overload prevents the address manager from being set up, which would later resolv*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 39. 🔴 REFUTED — [M] Nonce can be manipulated by inserting a contract creation `EthereumTx` message first in an SDK TX with multiple `EthereumTX` messages

- Corpus: `2024-11-nibiru` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "monotonicity",
      "name": "nonce_strictly_increments",
      "solidity_expr": "nonce_after == nonce_before + 1",
      "quantities_involved": [
        "nonce",
        "msg.sender"
      ],
      "violation_pattern": "contract creation message in multi-message SDK TX increments nonce out of sequence, allowing later messages to manipulate expected nonce values",
      "actions_required": [
        "executeTransaction"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "ordering",
      "name": "nonce_committed_before_execution",
      "solidity_expr": "nonce_reserved == nonce_before + execution_index",
      "quantities_involved": [
        "nonce",
        "execution_index"
      ],
      "violation_pattern": "nonce increment occurs during contract creation execution instead of at message validation time, breaking deterministic nonce assignment in multi-message batch",
      "actions_required": [
        "validateMessages",
        "executeTransaction"
      ],
      "scope": "cross_function",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariants describe expected correct behavior (nonce should increment by 1, nonce should be reserved before execution) but the bug is about nonce manipulation through out-of-sequence increments in multi-message batches, which could still satisfy 'nonce_after == nonce_before + 1' for individual m"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariants describe expected correct behavior (nonce should increment by 1, nonce should be reserved before execution) but the bug is about nonce manipulation through out-of-sequence increments in multi-message batches, which could still satisfy 'nonce_after == nonce_before + 1' for individual m*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 40. 🔴 REFUTED — [M] `_internalRemoteTransferSendPacket()` can't send the difference back to the user

- Corpus: `2024-02-tapioca` (source: c4)
- Body: **Mechanism:** The difference token be left in the contract.

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "difference_returned_to_user",
      "solidity_expr": "user_balance_after == user_balance_before + (amount_in - amount_used)",
      "quantities_involved": [
        "user_balance",
        "contract_balance",
        "amount_in",
        "amount_used"
      ],
      "violation_pattern": "internalRemoteTransferSendPacket consumes partial amount but leaves difference in contract instead of returning to caller",
      "actions_required": [
        "internalRemoteTransferSendPacket"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "no_locked_user_funds",
      "solidity_expr": "contract_balance_after <= contract_balance_before - (amount_in - amount_used)",
      "quantities_involved": [
        "contract_balance",
        "amount_in",
        "amount_used"
      ],
      "violation_pattern": "difference tokens remain locked in contract balance instead of being refunded",
      "actions_required": [
        "internalRemoteTransferSendPacket"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The second invariant's direction is incorrect: if the difference remains locked in the contract, the contract balance should INCREASE (not decrease), so `contract_balance_after >= contract_balance_before + (amount_in - amount_used)` would be violated, not the stated inequality."
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The second invariant's direction is incorrect: if the difference remains locked in the contract, the contract balance should INCREASE (not decrease), so `contract_balance_after >= contract_balance_before + (amount_in - amount_used)` would be violated, not the stated inequality.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 41. 🔴 REFUTED — [M] Fee inclusivity calculations are inaccurate in `RubiconMarket`

- Corpus: `2023-04-rubicon` (source: c4)
- Body: **Mitigation:** The correct calculation for the fee inclusivity amount should be as follows:

    result = amount / (100% + protocol fee + maker fee)

For the example given in the previous section, this would result in an amount of `1000 / (100% + 10% + 5%) = 869`.

**[daoio (Rubicon) confirmed](https://github.com/code-423n4/2023-04-rubicon-findings/issues/1312#issuecomment-1532482649)**

**[Hicku...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "fee_inclusive_amount_correct",
      "solidity_expr": "amountAfterFee * (BPS + protocolFee + makerFee) == amountBefore * BPS",
      "quantities_involved": [
        "amountAfterFee",
        "amountBefore",
        "protocolFee",
        "makerFee",
        "BPS"
      ],
      "violation_pattern": "calcAmountAfterFee uses incorrect fee inclusivity formula; protocol and maker receive less fees than intended when amount includes fees",
      "actions_required": [
        "calcAmountAfterFee"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "total_fees_extracted_correctly",
      "solidity_expr": "protocolFeeCollected + makerFeeCollected == amountBefore - amountAfterFee",
      "quantities_involved": [
        "protocolFeeCollected",
        "makerFeeCollected",
        "amountBefore",
        "amountAfterFee"
      ],
      "violation_pattern": "incorrect fee calculation causes mismatch between amount deducted and fees actually collected by protocol and maker",
      "actions_required": [
        "calcAmountAfterFee"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The first invariant `amountAfterFee * (BPS + protocolFee + makerFee) == amountBefore * BPS` is the CORRECT relationship that should hold after proper fee calculation, but the bug is that the existing code violates this invariant by using an incorrect formula, meaning this invariant would fail in the"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant `amountAfterFee * (BPS + protocolFee + makerFee) == amountBefore * BPS` is the CORRECT relationship that should hold after proper fee calculation, but the bug is that the existing code violates this invariant by using an incorrect formula, meaning this invariant would fail in the*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 42. ✅ CLEAN — [H] `erc721DecreaseIsolateSupplyOnLiquidate()` missing clear `lockerAddr`

- Corpus: `2024-07-benddao` (source: c4)
- Body: **Mechanism:** Unable to retrieve NFT.

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "ordering",
      "name": "clear_locker_on_liquidate",
      "solidity_expr": "lockerAddr[tokenId] == address(0)",
      "quantities_involved": [
        "lockerAddr",
        "tokenId",
        "isolateSupply"
      ],
      "violation_pattern": "liquidation decreases isolateSupply but fails to clear lockerAddr mapping, leaving stale pointer that prevents NFT retrieval",
      "actions_required": [
        "liquidate"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "conservation",
      "name": "isolate_supply_matches_locked_tokens",
      "solidity_expr": "isolateSupply == countNonZeroLockers()",
      "quantities_involved": [
        "isolateSupply",
        "lockerAddr"
      ],
      "violation_pattern": "isolateSupply decremented without clearing corresponding lockerAddr entry creates mismatch between tracked count and actual locked tokens",
      "actions_required": [
        "liquidate"
      ],
      "scope": "contract_invariant",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": false,
    "reason": "Both invariants correctly capture the bug: the first as a postcondition that lockerAddr must be cleared after liquidation, and the second as a global invariant that isolateSupply should match the count of locked tokens, both of which are violated when liquidation decrements isolateSupply without cle"
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *Both invariants correctly capture the bug: the first as a postcondition that lockerAddr must be cleared after liquidation, and the second as a global invariant that isolateSupply should match the count of locked tokens, both of which are violated when liquidation decrements isolateSupply without cle*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 43. 🔴 REFUTED — [H] Forcing Starknet handlers to be whitelisted on the same chain allows exploit of `BurnUnlock` mode to drain handler funds

- Corpus: `2024-08-chakra` (source: c4)
- Body: **Mechanism:** In Cairo contracts, when handling cross-chain messages or callbacks, the contract ensures that the handler on the same chain (Starknet) is whitelisted:

```rs
fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{

        assert(to_handler...

**Extracted invariant:**

```json
{
  "extractable": "PARTIAL",
  "driver_shape": "scripted_trace",
  "resistant_reason": "requires_cross_chain_state",
  "structural_invariants": [
    {
      "category": "conservation",
      "name": "burn_unlock_conservation",
      "solidity_expr": "burned_amount == unlocked_amount && from_chain != to_chain",
      "quantities_involved": [
        "burned_amount",
        "unlocked_amount",
        "from_chain",
        "to_chain"
      ],
      "violation_pattern": "BurnUnlock mode allows same-chain messages where tokens are burned then unlocked without cross-chain transfer, creating value from handler reserves",
      "actions_required": [
        "send_cross_chain_msg_same_chain",
        "receive_cross_chain_msg"
      ],
      "scope": "cross_function",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "cross_chain_msg_requires_different_chain",
      "solidity_expr": "from_chain != to_chain",
      "quantities_involved": [
        "from_chain",
        "to_chain"
      ],
      "violation_pattern": "handler whitelists itself on same chain, enabling attacker to send same-chain messages that bypass cross-chain burn-unlock semantics",
      "actions_required": [
        "receive_cross_chain_msg"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "handler_reserves_cover_unlocks",
      "solidity_expr": "handler_balance >= pending_unlocks",
      "quantities_involved": [
        "token.balanceOf(handler)",
        "pending_unlocks"
      ],
      "violation_pattern": "repeated same-chain burn-unlock cycles drain handler reserves as each receive unlocks tokens without corresponding cross-chain lock",
      "actions_required": [
        "send_cross_chain_msg_same_chain",
        "receive_cross_chain_msg"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 4"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'burn_unlock_conservation' requires 'burned_amount == unlocked_amount && from_chain != to_chain', but when the bug fires (same-chain messages where from_chain == to_chain), this invariant is NOT violated because burned_amount still equals unlocked_amount \u2014 the bug allows draining"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'burn_unlock_conservation' requires 'burned_amount == unlocked_amount && from_chain != to_chain', but when the bug fires (same-chain messages where from_chain == to_chain), this invariant is NOT violated because burned_amount still equals unlocked_amount — the bug allows draining*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 44. ✅ CLEAN — [H] Tombstoned observer can maliciously add a duplicate observer address resulting in forfeiting voting rewards of targeted observers

- Corpus: `2023-11-zetachain` (source: c4)
- Body: 

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "no_duplicate_observers",
      "solidity_expr": "observerCount[observerAddress] <= 1",
      "quantities_involved": [
        "observerList",
        "observerCount",
        "observerAddress"
      ],
      "violation_pattern": "tombstoned observer retains add privileges and inserts duplicate observer addresses into list, causing voting rewards to be split or forfeited for victims",
      "actions_required": [
        "addObserver"
      ],
      "scope": "contract_invariant",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "tombstoned_cannot_modify",
      "solidity_expr": "isTombstoned[msg.sender] == false",
      "quantities_involved": [
        "isTombstoned",
        "msg.sender"
      ],
      "violation_pattern": "tombstoned observer's authorization not revoked for addObserver call, allowing malicious modification of observer set",
      "actions_required": [
        "addObserver"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": false,
    "reason": "Both invariants correctly capture the bug's essence: a tombstoned observer should not be able to add observers (second invariant), and observers should not appear duplicately in the list (first invariant), which are precisely the properties violated according to the bug description."
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *Both invariants correctly capture the bug's essence: a tombstoned observer should not be able to add observers (second invariant), and observers should not appear duplicately in the list (first invariant), which are precisely the properties violated according to the bug description.*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 45. ✅ CLEAN — [H] Malicious borrowers will never repay loans with high interest

- Corpus: `2024-04-lavarage` (source: c4)
- Body: **Mitigation:** Consider adding the owed interest to the total amount when performing the liquidation check.

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "solvency",
      "name": "liquidation_threshold_includes_interest",
      "solidity_expr": "collateralValue * liquidationThreshold >= principal + accruedInterest",
      "quantities_involved": [
        "collateralValue",
        "principal",
        "accruedInterest",
        "liquidationThreshold"
      ],
      "violation_pattern": "liquidation check compares collateral only against principal, ignoring accrued interest; borrower remains solvent on-chain while actual debt exceeds collateral",
      "actions_required": [
        "borrow",
        "accrue_interest",
        "check_liquidation"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "underwater_position_liquidatable",
      "solidity_expr": "collateralValue * liquidationThreshold < totalDebt implies canLiquidate == true",
      "quantities_involved": [
        "collateralValue",
        "totalDebt",
        "canLiquidate"
      ],
      "violation_pattern": "liquidation authorization gate omits interest component from debt calculation; economically insolvent positions remain unliquidatable",
      "actions_required": [
        "borrow",
        "accrue_interest",
        "liquidate"
      ],
      "scope": "contract_invariant",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": false,
    "reason": "Both invariants precisely capture the bug's violation: liquidation checks exclude accrued interest from debt calculations, allowing economically insolvent positions to avoid liquidation, and the structural properties (solvency category, quantities involved, violation patterns) accurately match the d"
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *Both invariants precisely capture the bug's violation: liquidation checks exclude accrued interest from debt calculations, allowing economically insolvent positions to avoid liquidation, and the structural properties (solvency category, quantities involved, violation patterns) accurately match the d*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 46. 🔴 REFUTED — [M] VotiumStrategy withdrawal queue fails to consider available unlocked tokens causing different issues in the withdraw process

- Corpus: `2023-09-asymmetry` (source: c4)
- Body: **Mechanism:** VotiumStrategy withdrawals are executed in queue since the underlying CVX tokens may be locked in the Convex platform. Depositors must request a withdrawal and wait in queue until the epoch associated with their withdrawal is reached in order to exit their position. The core of this logic is present in the function `requestWithdraw()`:

<https://github.com/code-423n4/2023-09-asymmet...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "stateful_invariant",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "solvency",
      "name": "queue_position_respects_available_balance",
      "solidity_expr": "cvxUnlockObligations <= unlockable + cvxBalance + sum(lockedBalances[i].amount)",
      "quantities_involved": [
        "cvxUnlockObligations",
        "unlockable",
        "cvxBalance",
        "lockedBalances"
      ],
      "violation_pattern": "withdrawal queue assigns epoch based on locked+unlockable only, ignoring already-unlocked CVX balance, causing premature queue assignment",
      "actions_required": [
        "deposit",
        "requestWithdraw",
        "requestWithdraw"
      ],
      "scope": "contract_invariant",
      "halmos_directives": [
        "--loop 8",
        "--solver-timeout-assertion 10000"
      ]
    },
    {
      "category": "ordering",
      "name": "available_tokens_processed_before_locked",
      "solidity_expr": "withdrawEpoch == currentEpoch || (unlockable + cvxBalance < cvxUnlockObligations)",
      "quantities_involved": [
        "withdrawEpoch",
        "currentEpoch",
        "unlockable",
        "cvxBalance",
        "cvxUnlockObligations"
      ],
      "violation_pattern": "loop starts accumulating from unlockable without first depleting available CVX balance, causing incorrect epoch calculation",
      "actions_required": [
        "requestWithdraw"
      ],
      "scope": "function_postcondition",
      "halmos_directives": [
        "--loop 8"
      ]
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The first invariant 'cvxUnlockObligations <= unlockable + cvxBalance + sum(lockedBalances[i].amount)' actually HOLDS even when the bug fires, because the bug is not that obligations exceed total assets, but that the loop incorrectly calculates which epoch to assign by not accounting for already-avai"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant 'cvxUnlockObligations <= unlockable + cvxBalance + sum(lockedBalances[i].amount)' actually HOLDS even when the bug fires, because the bug is not that obligations exceed total assets, but that the loop incorrectly calculates which epoch to assign by not accounting for already-avai*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 47. ✅ CLEAN — [M] Lack of data validation when users are claiming their art allows malicious user to bypass signature/merkle hash to provide unapproved `ref_`, `artId_` and `imageURI`

- Corpus: `2024-08-phi` (source: c4)
- Body: **Mitigation:** In function `merkleClaim`:

```diff
if (
    !MerkleProofLib.verifyCalldata(
-       proof_, credMerkleRootHash, keccak256(bytes.concat(keccak256(abi.encode(minter_, leafPart_))))
+       proof_, credMerkleRootHash, keccak256(bytes.concat(keccak256(abi.encode(minter_, ref_, artId_, mintArgs_.imageURI, leafPart_))))
  )
) {
    revert InvalidMerkleProof();
}
```

In function `signat...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "merkle_proof_binds_all_claim_params",
      "solidity_expr": "MerkleProofLib.verifyCalldata(proof, root, keccak256(abi.encode(minter, ref, artId, imageURI, leafPart)))",
      "quantities_involved": [
        "proof",
        "credMerkleRootHash",
        "minter",
        "ref",
        "artId",
        "imageURI",
        "leafPart"
      ],
      "violation_pattern": "merkle proof only authenticates minter and leafPart; attacker supplies arbitrary ref, artId, imageURI that were never approved in the merkle tree",
      "actions_required": [
        "merkleClaim"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "authorization",
      "name": "signature_binds_all_claim_params",
      "solidity_expr": "ecrecover(digest, v, r, s) == verifier && keccak256(encodeData) == keccak256(abi.encode(expiresIn, minter, ref, verifier, artId, quantity, data, imageURI))",
      "quantities_involved": [
        "encodeData",
        "digest",
        "verifier",
        "minter",
        "ref",
        "artId",
        "imageURI"
      ],
      "violation_pattern": "signature validates encodeData but imageURI is read from mintArgs not encodeData; attacker supplies arbitrary imageURI outside signed commitment",
      "actions_required": [
        "signatureClaim"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": false,
    "reason": "The invariants accurately capture that the bug allows arbitrary ref, artId, and imageURI to bypass authentication because these parameters are not included in the merkle proof verification (first invariant) and imageURI is not included in the signed encodeData (second invariant), making them precise"
  }
}
```

**Adversarial critic verdict:** `refuted=False` — *The invariants accurately capture that the bug allows arbitrary ref, artId, and imageURI to bypass authentication because these parameters are not included in the merkle proof verification (first invariant) and imageURI is not included in the signed encodeData (second invariant), making them precise*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 48. 🔴 REFUTED — [M] `MagicLpAggregator` can be incompatible with potential integrators due to incorrect `latestRoundData` function

- Corpus: `2024-03-abracadabra-money` (source: c4)
- Body: **Mitigation:** Use the values `roundId`, `startAt`, `updatedAt` and `answeredInRound` from whichever oracle, `baseOracle` or `quoteOracle` was used.

**[rexjoseph (Warden) commented](https://github.com/code-423n4/2024-03-abracadabra-money-findings/issues/93#issuecomment-2034370525):**
> I think we should reiterate the issue here as the submission has tried its best to point out:
> 
> 1. The `Magi...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "oracle_sanity",
      "name": "updated_at_reflects_oracle_freshness",
      "solidity_expr": "updatedAt_returned >= baseOracle_updatedAt || updatedAt_returned >= quoteOracle_updatedAt",
      "quantities_involved": [
        "updatedAt",
        "baseOracle.latestRoundData",
        "quoteOracle.latestRoundData"
      ],
      "violation_pattern": "latestRoundData hardcodes updatedAt to 0 instead of propagating the timestamp from the underlying baseOracle or quoteOracle, causing integrators' staleness checks to always revert",
      "actions_required": [
        "latestRoundData"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "oracle_sanity",
      "name": "round_id_reflects_oracle_state",
      "solidity_expr": "roundId_returned == baseOracle_roundId || roundId_returned == quoteOracle_roundId",
      "quantities_involved": [
        "roundId",
        "baseOracle.latestRoundData",
        "quoteOracle.latestRoundData"
      ],
      "violation_pattern": "latestRoundData hardcodes roundId to 0 instead of propagating the value from the underlying oracle, breaking integrator assumptions about round progression",
      "actions_required": [
        "latestRoundData"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "oracle_sanity",
      "name": "answered_in_round_reflects_oracle_state",
      "solidity_expr": "answeredInRound_returned == baseOracle_answeredInRound || answeredInRound_returned == quoteOracle_answeredInRound",
      "quantities_involved": [
        "answeredInRound",
        "baseOracle.latestRoundData",
        "quoteOracle.latestRoundData"
      ],
      "violation_pattern": "latestRoundData hardcodes answeredInRound to 0 instead of propagating the value from the underlying oracle, preventing integrators from detecting incomplete rounds",
      "actions_required": [
        "latestRoundData"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The invariants use disjunction (OR) which allows them to hold even when the bug fires, since if updatedAt_returned is hardcoded to 0, the condition 'updatedAt_returned >= baseOracle_updatedAt || updatedAt_returned >= quoteOracle_updatedAt' can still be satisfied when baseOracle_updatedAt is also 0, "
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariants use disjunction (OR) which allows them to hold even when the bug fires, since if updatedAt_returned is hardcoded to 0, the condition 'updatedAt_returned >= baseOracle_updatedAt || updatedAt_returned >= quoteOracle_updatedAt' can still be satisfied when baseOracle_updatedAt is also 0, *

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 49. 🔴 REFUTED — [H] `triggerFee` is stolen from other auctions during `settleWithBuyout()`

- Corpus: `2024-04-gondi` (source: c4)
- Body: **Mitigation:** Consider using `safeTransferFrom()` to pay the `triggerFee` from the sender's address, rather than using `safeTransfer()` to pay the `triggerFee` from the contract balance.

**[0xend (Gondi) confirmed](https://github.com/code-423n4/2024-04-gondi-findings/issues/50#event-12543486840)**

**[0xA5DF (judge) commented](https://github.com/code-423n4/2024-04-gondi-findings/issues/50#issue...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "fee_paid_from_msg_sender",
      "solidity_expr": "token.balanceOf(msg.sender) == sender_balance_before - triggerFee",
      "quantities_involved": [
        "token.balanceOf(msg.sender)",
        "triggerFee"
      ],
      "violation_pattern": "settleWithBuyout uses safeTransfer from contract balance instead of safeTransferFrom msg.sender, pulling triggerFee from pooled funds belonging to other auctions",
      "actions_required": [
        "settleWithBuyout"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    },
    {
      "category": "solvency",
      "name": "contract_balance_not_depleted_by_other_user_fee",
      "solidity_expr": "token.balanceOf(address(this)) >= reserved_balance_for_other_auctions",
      "quantities_involved": [
        "token.balanceOf(address(this))",
        "reserved_balance_for_other_auctions"
      ],
      "violation_pattern": "paying triggerFee from contract balance drains funds reserved for other auctions, creating shortfall when those auctions settle",
      "actions_required": [
        "settleWithBuyout"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.92,
  "validation": {
    "refuted": true,
    "reason": "The first invariant `fee_paid_from_msg_sender` would fail even when the bug is NOT present (when correctly using safeTransferFrom), because safeTransferFrom transfers from msg.sender TO the contract first, then the contract pays the fee recipient, so msg.sender's balance would decrease but the invar"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The first invariant `fee_paid_from_msg_sender` would fail even when the bug is NOT present (when correctly using safeTransferFrom), because safeTransferFrom transfers from msg.sender TO the contract first, then the contract pays the fee recipient, so msg.sender's balance would decrease but the invar*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

## 50. 🔴 REFUTED — [M] `DualVmToken` can be abused to cause RPC-level reverts by revoking native token approval to Kakarot

- Corpus: `2024-09-kakarot` (source: c4)
- Body: **Mitigation:** Consider adding the following check to the `DualVmToken.approve` function:

```Solidity
    require(spender != kakarot);
```

**[ClementWalter (Kakarot) confirmed and commented](https://github.com/code-423n4/2024-09-kakarot-findings/issues/48#issuecomment-2451963306):**
 > Severity: Low<br>
 > This is a low issue as there is no clear external attack path. A user would need to decid...

**Extracted invariant:**

```json
{
  "extractable": "CLEAN_SAFETY",
  "driver_shape": "single_tx_check",
  "resistant_reason": null,
  "structural_invariants": [
    {
      "category": "authorization",
      "name": "kakarot_approval_immutable",
      "solidity_expr": "spender != kakarot_address",
      "quantities_involved": [
        "spender",
        "kakarot_address",
        "allowance"
      ],
      "violation_pattern": "approve function allows caller to set kakarot approval to zero, blocking native token operations and causing RPC-level reverts",
      "actions_required": [
        "approve"
      ],
      "scope": "function_postcondition",
      "halmos_directives": []
    }
  ],
  "confidence": 0.88,
  "validation": {
    "refuted": true,
    "reason": "The invariant 'spender != kakarot_address' states that the spender should never equal kakarot, but the bug is specifically about setting approval *to zero* for kakarot (not merely calling approve with kakarot as spender), so the invariant would fail even for legitimate non-zero approvals to kakarot,"
  }
}
```

**Adversarial critic verdict:** `refuted=True` — *The invariant 'spender != kakarot_address' states that the spender should never equal kakarot, but the bug is specifically about setting approval *to zero* for kakarot (not merely calling approve with kakarot as spender), so the invariant would fail even for legitimate non-zero approvals to kakarot,*

**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong

---

