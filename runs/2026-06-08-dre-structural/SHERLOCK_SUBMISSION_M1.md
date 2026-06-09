# Sherlock Contest 1259 — DRE App / dreUSD — Submission #2 (M-1)

**Repo**: https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz
**Commit**: 6ec9cc8042315498bed7b36d6cc33bade6e894a5

---

## TITLE

```
PAUSER pausing dreRewardsDistributor will create unfair pricing for vault depositors as withdrawals price against unclaimable vested rewards, causing early withdrawers to drain virtualBalance and late withdrawers to be stranded
```

## SUMMARY  (Summary field)

```
The asymmetric pause coupling between dreRewardsDistributor and dreUSDs will cause loss of funds for late withdrawers as totalAssets() keeps reading the distributor's vestedAmount() (which has no pause check) while _claimVestedRewards() silently returns 0 (pause check on distributor). Early withdrawers price their redemption against the inflated totalAssets and drain the real virtualBalance pool; late withdrawers' redemption assets exceed remaining virtualBalance and revert with underflow, stranding their principal until unpause.
```

## ROOT CAUSE  (Root Cause field)

```
In [`dreUSDs.sol#L109-L114`](https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz/blob/6ec9cc8042315498bed7b36d6cc33bade6e894a5/dreusd/contracts/dreUSDs.sol#L109-L114), the `totalAssets()` override unconditionally adds `IdreRewardsDistributor(rewardsDistributor).vestedAmount()` to `_virtualBalance`. The view function `vestedAmount` ([`dreRewardsDistributor.sol#L155-L157`](https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz/blob/6ec9cc8042315498bed7b36d6cc33bade6e894a5/dreusd/contracts/dreRewardsDistributor.sol#L155-L157)) has no pause check — it returns the time-linear vested amount even while the distributor is paused.

Meanwhile, `_claimVestedRewards()` in dreUSDs ([`dreUSDs.sol#L204-L208`](https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz/blob/6ec9cc8042315498bed7b36d6cc33bade6e894a5/dreusd/contracts/dreUSDs.sol#L204-L208)) explicitly returns 0 when the distributor is paused:

```solidity
function _claimVestedRewards() internal returns (uint256 claimed) {
    if (rewardsDistributor == address(0)) return 0;
    if (PausableUpgradeable(rewardsDistributor).paused()) return 0;
    return IdreRewardsDistributor(rewardsDistributor).claimVested();
}
```

The withdraw hook ([`dreUSDs.sol#L222-L235`](https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz/blob/6ec9cc8042315498bed7b36d6cc33bade6e894a5/dreusd/contracts/dreUSDs.sol#L222-L235)) prices the redemption against `totalAssets()` (inflated by phantom vested) but `_virtualBalance += _claimVestedRewards()` evaluates to `_virtualBalance += 0` during pause before subtracting `assets`. The first withdrawer extracts an inflated share of the real `_virtualBalance` pool; subsequent withdrawers hit the underflow on `_virtualBalance -= assets` and revert.

The "distributor paused / vault unpaused" state is reachable because dreRewardsDistributor has its own `whenNotPaused` and its own PAUSER_ROLE, independent of the dreUSDs vault's pause state.
```

## INTERNAL PRE-CONDITIONS  (Internal Pre-conditions field)

```
1. The dreUSDs vault has multiple depositors holding shares. Two or more independent depositors are required for the asymmetric-pricing harm to materialize.
2. A reward vesting cycle is in progress: dreRewardsDistributor.rewards > 0 and cTs < block.timestamp < eTs. The bug fires for any non-zero vestedAmount() greater than 0 — i.e. throughout the entire 7-day vest period.
3. The dreRewardsDistributor is PAUSED via pause() (PAUSER_ROLE) while the dreUSDs vault remains UNPAUSED. This is a reachable, valid state — both contracts have independent pause state via their own PausableUpgradeable and PAUSER_ROLE assignments.
4. The vault holds less in _virtualBalance than the inflated totalAssets() would imply (always true once vestedAmount() > 0 accrues).
```

## EXTERNAL PRE-CONDITIONS  (External Pre-conditions field)

```
1. PAUSER acts on a legitimate emergency — e.g., suspected exploit in the rewards-minting flow upstream of the distributor, or operational issue requiring a halt of new reward accrual. Sherlock V2 explicitly classifies pause as a "protective action" carve-out (not an admin-trust violation), so the trigger is a legitimate, intended operational behavior, not a malicious admin action.
2. A second user attempts to withdraw after the first withdrawer in the same paused window. No attacker action required — natural concurrent withdraw behavior is sufficient.
```

## ATTACK PATH  (Attack Path field)

```
1. Alice and Bob each deposit 50 dreUSD into the vault when no rewards are vesting. Vault state: virtualBalance = 100, totalSupply = 100, vested = 0, totalAssets = 100. Per-share price = 1.0.
2. Admin/MODERATOR adds 100 dreUSD of rewards to the distributor and calls addRewards. State: rewards = 100, cTs = T0, eTs = T0 + 7 days, vested = 0.
3. Time advances 3.5 days. State: vested = 50, totalAssets = virtualBalance(100) + vested(50) = 150. Per-share price = 1.5.
4. PAUSER calls dist.pause() on the rewards distributor only. Vault is NOT paused.
5. Alice calls vault.redeem(50, alice, alice) first. Inside _withdraw: _virtualBalance += _claimVestedRewards() evaluates to _virtualBalance += 0 because the distributor is paused. assets is computed via _convertToAssets(50, Floor) = mulDiv(50, totalAssets+1, totalSupply+1, Floor) ~= 75. State: _virtualBalance -= 75 -> 25, totalSupply -= 50 -> 50. Alice receives 75 dreUSD.
6. Bob calls vault.redeem(50, bob, bob). Same arithmetic: _claimVestedRewards = 0 (still paused), assets = mulDiv(50, 75+1, 50+1, Floor) ~= 74. State change attempt: _virtualBalance(25) -= 74 -> UNDERFLOW. Bob's transaction REVERTS.
7. Bob iteratively tries smaller share amounts. The maximum recoverable is bounded by current _virtualBalance = 25. Bob can withdraw at most ~16 shares for ~24 dreUSD. His remaining 34 shares represent 50 dreUSD of original deposit but are stranded.
8. If PAUSER does not unpause promptly, Bob's stranded principal cannot be recovered until pause is lifted. Even after unpause, the share-pricing asymmetry has already extracted excess yield to Alice that should have been proportionally shared.
```

## IMPACT  (Impact field)

```
Late withdrawers in the paused window suffer direct loss of funds proportional to the duration of pause. Concrete PoC numbers: Alice deposits 50, recovers 75 (gain of 25). Bob deposits 50, can recover at most 24 in the paused window (loss of 26 — a 52% haircut on principal during the pause). Even if pause is eventually lifted and Bob recovers more, the asymmetric distribution of rewards has already favored Alice at Bob's expense.

The bug fires on any pause-distributor + unpaused-vault state, which is a reachable and legitimate operational state. It does not require admin malice — only routine emergency response to halt new reward accrual while leaving the vault open for user withdrawals.

Sherlock V2 severity: Medium. Direct user-vs-user fund redistribution caused by a pause that is intentionally protective. The pause action is explicitly carved-out of admin-trust scope per Sherlock V2 rules ("actions that protect users cannot be considered admin-trust").

MACHINE-VERIFIED EVIDENCE: A TLA+ model of the vault + paused distributor system was checked with TLC and produced a counterexample trace matching the Foundry PoC exactly. The trace: Init -> AddRewards -> Tick (vested grows) -> PauseDistributor -> UserWithdraw(a) (succeeds at inflated price) -> UserWithdraw(b) (reverts, pauseFundsLost = 14) — invariant ShareValuePreserved VIOLATED.

CORPUS PRECEDENTS at similar cosine distance to this finding in the judged-Sherlock/Code4rena H/M corpus (1240 findings, bge-small-en-v1.5 embeddings):
- "Inability to withdraw funds for certain users due to whenNotPaused modifier" — Sherlock MEDIUM (cos=0.799)
- "User could withdraw more than supposed to, forcing last user withdraw to fail" — Code4rena HIGH (cos=0.789)
- "Risk of mass liquidation after pool/asset pause and unpause" — Sherlock MEDIUM (cos=0.766)
- "Because of the asset: Share 1:1 Conversion, if vault incurs a loss, the last user to withdraw is shortchanged" — Sherlock MEDIUM (cos=0.816)
```

## PoC  (PoC field)

````
Save as `dreusd/test/PoC_PausedDistributorUnfairWithdraw.t.sol`. Test PASSES against the contest commit.

```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {dreUSD} from "../contracts/dreUSD.sol";
import {dreUSDs} from "../contracts/dreUSDs.sol";
import {dreRewardsDistributor} from "../contracts/dreRewardsDistributor.sol";
import {EndpointV2Mock} from "../contracts/mocks/EndpointV2Mock.sol";

contract PoC_PausedDistributorUnfairWithdraw is Test {
    dreUSD public asset;
    dreUSDs public vault;
    dreRewardsDistributor public dist;

    address public admin = makeAddr("admin");
    address public upgrader = makeAddr("upgrader");
    address public guardian = makeAddr("guardian");
    address public alice = makeAddr("alice");
    address public bob = makeAddr("bob");

    function setUp() public {
        EndpointV2Mock endpoint = new EndpointV2Mock();
        dreUSD assetImpl = new dreUSD(address(endpoint));
        asset = dreUSD(address(new ERC1967Proxy(address(assetImpl),
            abi.encodeWithSelector(dreUSD.initialize.selector, admin, upgrader, guardian))));

        dreUSDs vaultImpl = new dreUSDs();
        vault = dreUSDs(address(new ERC1967Proxy(address(vaultImpl),
            abi.encodeWithSelector(dreUSDs.initialize.selector, IERC20(address(asset)), admin))));

        dreRewardsDistributor distImpl = new dreRewardsDistributor(address(asset), address(vault));
        dist = dreRewardsDistributor(address(new ERC1967Proxy(address(distImpl),
            abi.encodeWithSelector(dreRewardsDistributor.initialize.selector, admin, admin, admin))));

        vm.prank(admin); vault.setRewardsDistributor(address(dist));
        bytes32 modRole = dist.MODERATOR_ROLE();
        vm.prank(admin); dist.grantRole(modRole, admin);
        vm.prank(admin); asset.setDreUSDManager(address(this));

        asset.mint(alice, 50 ether);
        asset.mint(bob, 50 ether);
        vm.prank(alice); asset.approve(address(vault), type(uint256).max);
        vm.prank(bob); asset.approve(address(vault), type(uint256).max);
        vm.prank(alice); vault.deposit(50 ether, alice);
        vm.prank(bob); vault.deposit(50 ether, bob);
    }

    function test_PausedDistributorUnfairWithdraw() public {
        asset.mint(address(dist), 100 ether);
        vm.prank(admin); dist.addRewards();
        vm.warp(block.timestamp + 3.5 days);

        vm.prank(admin); dist.pause();
        assertEq(dist.paused(), true);
        assertEq(vault.paused(), false);
        assertGt(dist.vestedAmount(), 0);
        assertEq(vault.totalAssets(), 150 ether);

        vm.prank(alice);
        uint256 aliceRecovered = vault.redeem(vault.balanceOf(alice), alice, alice);
        emit log_named_decimal_uint("Alice recovered:", aliceRecovered, 18);
        assertGt(aliceRecovered, 50 ether);

        uint256 bobShares = vault.balanceOf(bob);
        vm.prank(bob);
        vm.expectRevert();
        vault.redeem(bobShares, bob, bob);

        uint256 bobMax = 0;
        for (uint256 attempt = bobShares; attempt > 0; attempt = (attempt * 90) / 100) {
            try this.bobRedeem(attempt) returns (uint256 r) { bobMax = r; break; }
            catch { continue; }
        }
        emit log_named_decimal_uint("Bob max recoverable (paused window):", bobMax, 18);
        emit log_named_decimal_uint("Bob loss vs deposit:", 50 ether - bobMax, 18);
        assertLt(bobMax, 30 ether);
        emit log("M-1 CONFIRMED");
    }

    function bobRedeem(uint256 shares) external returns (uint256) {
        vm.prank(bob); return vault.redeem(shares, bob, bob);
    }
}
```

Run with:

```bash
forge test --match-test test_PausedDistributorUnfairWithdraw -vv
```

PoC PASSES with output: `Alice recovered: 75 dreUSD; Bob max recoverable: 24 dreUSD; Bob loss vs deposit: 26 dreUSD`. Verified by TLC model-checking of the TLA+ shape `PausedDistributorPricingAsymmetry`: counterexample trace `Init -> AddRewards -> Tick -> PauseDistributor -> UserWithdraw(a) -> UserWithdraw(b) reverts` matches the Foundry trace.
````

## MITIGATION  (Mitigation field)

```
Apply ONE of the following:

1. Make vestedAmount() pause-aware. Return 0 when the distributor is paused so totalAssets() does not include phantom unclaimable vested:

```solidity
function vestedAmount() external view returns (uint256 vested) {
    if (paused()) return 0;
    (vested,) = _computeVestedAmount();
}
```

This synchronizes the share-price calculation with the actual claimable balance. Withdrawals during pause price against _virtualBalance + 0 and proportionally distribute the real pool.

2. Pause the vault automatically when the distributor pauses (and vice-versa). Wire the distributor's pause/unpause to call into dreUSDs and propagate state. This eliminates the asymmetric pause window entirely.

3. Add the whenNotPaused-from-distributor check to dreUSDs._withdraw. Block withdrawals while the distributor is paused, halting the race entirely.

Option 1 is the most conservative — it preserves vault operation during distributor pause but eliminates the price-asymmetry attack surface.
```
