# Sherlock Contest 1259 Submission — DRE App / dreUSDs (M-1)

**Repo**: https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz
**Commit**: 6ec9cc8 (Initial commit)
**Drafted**: 2026-06-08
**Submit via**: New Issue on contest repo using the audit-report template

Paste each section below into the matching YAML field in the issue form.

---

## TITLE

```
PAUSER pausing dreRewardsDistributor will cause unfair withdrawal lockup for vault depositors as withdrawals price against unclaimable vested rewards
```

---

## SUMMARY  (Summary field)

```
The absence of distributor-pause gating in `dreUSDs.totalAssets()` combined with the pause-skipping branch in `_claimVestedRewards()` will cause asymmetric loss of principal for late-withdrawing vault depositors as a holder of distributor `PAUSER_ROLE` pausing the distributor mid-vest leaves `vestedAmount()` inflating the vault's reported assets while the underlying reward transfer is silently skipped, so early redeemers price against phantom vested rewards and drain the actual `_virtualBalance` disproportionately, leaving late redeemers underflow-reverted and locked.
```

---

## ROOT CAUSE  (Root Cause field)

```
Three asymmetries in `dreusd/contracts/dreUSDs.sol` and `dreusd/contracts/dreRewardsDistributor.sol` line up to create a state where the share price is computed against assets that cannot actually be paid out:

1. In `dreusd/contracts/dreUSDs.sol#L109-L114` `totalAssets()` returns `_virtualBalance + rewardsDistributor.vestedAmount()` UNCONDITIONALLY — it does not consult `rewardsDistributor.paused()`.
2. In `dreusd/contracts/dreRewardsDistributor.sol#L155-L157` `vestedAmount()` is a `view` function with no pause-gating — it keeps returning the time-linear vested amount even after the distributor is paused.
3. In `dreusd/contracts/dreUSDs.sol#L204-L208` `_claimVestedRewards()` SKIPS the actual reward transfer when `rewardsDistributor.paused()` is true and returns `0`. Asymmetry: ERC-4626 pricing in `totalAssets()` includes the phantom vested amount, but the redeemer cannot actually pull it.
4. In `dreusd/contracts/dreUSDs.sol#L228-L232` `_withdraw` decrements `_virtualBalance -= assets` where `assets` is the ERC-4626-computed amount against the inflated `totalAssets`. Early redeemers therefore drain the real backing disproportionately. Late redeemers hit underflow on the same line and revert, trapping their shares until the distributor is unpaused.
5. In `dreusd/contracts/dreUSDs.sol#L144-L157` `maxWithdraw`/`maxRedeem` check only the vault's own pause flag, never the distributor's — so "distributor paused, vault unpaused" is a fully reachable and quote-able state.
```

---

## INTERNAL PRE-CONDITIONS  (Internal Pre-conditions field)

```
1. The vault `dreUSDs` has at least two depositors with non-trivial share balances at the moment the distributor is paused (otherwise there is no asymmetric victim — a single depositor would simply redeem against an inflated price with no second redeemer to underflow).
2. `dreRewardsDistributor.rewards > 0` and the vest window is currently active, i.e. `block.timestamp >= cTs` and `block.timestamp < eTs`, so `vestedAmount() > 0`.
3. `dreUSDs.rewardsDistributor` is set to the live `dreRewardsDistributor` (set during normal deployment via `dreUSDs.setRewardsDistributor`, `dreUSDs.sol#L78-L89`).
4. The distributor `PAUSER_ROLE` and the vault `PAUSER_ROLE` are SEPARATE roles (granted to separate addresses, or even the same address but actioned independently). Pausing the distributor does not auto-pause the vault.
```

---

## EXTERNAL PRE-CONDITIONS  (External Pre-conditions field)

```
1. The address holding distributor `PAUSER_ROLE` calls `dreRewardsDistributor.pause()` while a vest is in progress. This may be benign (incident-response circuit-breaker on the rewards path) or operationally accidental — the bug fires either way; no attacker-controlled action is required beyond the pause itself, which is the documented and intended capability of the role.
2. At least one vault depositor redeems while the distributor is paused before any other depositor. (Naturally satisfied: any depositor noticing yield has stopped will rationally exit, and the first to do so wins the inflated-price race.)
```

---

## ATTACK PATH  (Attack Path field)

```
1. Alice and Bob each deposit 50 dreUSD into the vault. `totalSupply = 100 shares`, `_virtualBalance = 100 dreUSD`.
2. KEEPER mints 100 dreUSD of rewards to the distributor and calls `addRewards()`. `rewards = 100`, vest window opens for 7 days.
3. 3.5 days elapse. `vestedAmount() ≈ 50 dreUSD`. `totalAssets() = 100 + 50 = 150`. Share price ≈ 1.5.
4. The address holding distributor `PAUSER_ROLE` invokes `dist.pause()` (e.g. for incident response on the rewards path). The vault is NOT paused; `vault.paused() == false`.
5. CRITICAL ASYMMETRY: `vestedAmount()` and therefore `totalAssets()` continue to report the inflated 150 because neither consults the distributor pause flag. But `_claimVestedRewards()` will now return 0 silently because of the distributor-pause branch.
6. Alice redeems all 50 shares. ERC-4626 prices them at `50 * 150 / 100 = 75 dreUSD`. `_virtualBalance` decrements from 100 to 25 — Alice has just drained 75% of the actual reserve against shares that ought to be worth half of the 100-dreUSD reserve plus half of an (unclaimable) 50-dreUSD vested pool.
7. Bob attempts to redeem his 50 shares. ERC-4626 prices them at `50 * 75 / 50 = 75 dreUSD` (totalAssets is still 25 + 50 vested = 75). `_virtualBalance -= 75` underflows on a `_virtualBalance` of 25 — the call reverts. Bob is unable to exit at any sane share count — a linear sweep shows his ceiling is roughly 25 dreUSD (the residual `_virtualBalance` left after Alice), against an original 50-dreUSD deposit.
8. Bob's shares remain locked until the distributor is unpaused. If the pause persists (intentional retire of the rewards channel, lengthy incident review, etc.) Bob is permanently down 26+ dreUSD of principal — a 52% haircut versus his original 50-dreUSD deposit.
```

---

## IMPACT  (Impact field)

```
Late-redeeming vault depositors lose principal as a direct consequence of an intended (and authorized) PAUSER action on a SEPARATE contract.

PoC numbers (from `test_PausedDistributorUnfairWithdraw`):
- Alice deposited 50 dreUSD; redeemed and received 74.999999999999999999 dreUSD (~75) — a 50% windfall.
- Bob deposited 50 dreUSD; full redeem REVERTS (underflow); coarse linear sweep shows max recoverable ≈ 24 dreUSD (actual ceiling ~25 = the `_virtualBalance` left after Alice).
- Bob's net loss: 26 dreUSD on a 50-dreUSD principal = 52% haircut, irrecoverable until the distributor is unpaused.
- 50 dreUSD of vested rewards is permanently stranded in the paused distributor for the duration of the pause.

This is a Sherlock V2 Medium: requires an admin action (distributor pause) to trigger, but causes direct loss of user principal in a non-extreme, fully reachable path. The PAUSER_ROLE is documented to act on the distributor independently of the vault; no protocol invariant says pausing the distributor must also pause the vault, and the maxWithdraw/maxRedeem quotes confirm the state is treated as live. The asymmetry is between two innocent depositors (whoever exits first wins; whoever exits second loses), not between a privileged actor and users — i.e. it is not "admin steals," it is "admin action causes user-vs-user redistribution and lockup."
```

---

## PoC  (PoC field)

````
Save as `dreusd/test/PoC_PausedDistributorUnfairWithdraw.t.sol`:

```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {dreUSD} from "../contracts/dreUSD.sol";
import {dreUSDs} from "../contracts/dreUSDs.sol";
import {dreRewardsDistributor} from "../contracts/dreRewardsDistributor.sol";
import {dreUSDManager} from "../contracts/dreUSDManager.sol";
import {EndpointV2Mock} from "../contracts/mocks/EndpointV2Mock.sol";
import {DreUSDOracleMock} from "../contracts/mocks/DreUSDOracleMock.sol";
import {WithdrawalNFTMock} from "../contracts/mocks/WithdrawalNFTMock.sol";
import {MockERC20} from "../contracts/mocks/MockERC20.sol";

/**
 * @title PoC_PausedDistributorUnfairWithdraw
 * @notice Demonstrates M-1: When dreRewardsDistributor is paused mid-vest:
 *   - vestedAmount() has NO pause check, keeps reporting accrued amount
 *   - _claimVestedRewards() returns 0 silently (line 206 has pause check)
 *   - totalAssets() = _virtualBalance + vestedAmount() reports INFLATED value
 *   - Early withdrawers price against inflated totalAssets and drain disproportionate
 *     share of the actual _virtualBalance (which stays flat)
 *   - Late withdrawers hit underflow on _virtualBalance -= assets and REVERT,
 *     permanently locked until unpause
 */
contract PoC_PausedDistributorUnfairWithdraw is Test {
    dreUSD public asset;
    dreUSDs public vault;
    dreRewardsDistributor public dist;
    dreUSDManager public manager;
    DreUSDOracleMock public oracle;
    WithdrawalNFTMock public expressNFT;
    WithdrawalNFTMock public standardNFT;
    MockERC20 public usdc;

    address public admin = makeAddr("admin");
    address public upgrader = makeAddr("upgrader");
    address public guardian = makeAddr("guardian");
    address public moderator = makeAddr("moderator");
    address public withdrawalConfig = makeAddr("withdrawalConfig");
    address public pauser = makeAddr("pauser");
    address public keeper = makeAddr("keeper");
    address public expressOperator = makeAddr("expressOperator");
    address public treasury = makeAddr("treasury");
    address public expressPayback = makeAddr("expressPayback");
    address public expressFeeRecipient = makeAddr("expressFeeRecipient");

    address public alice = makeAddr("alice");
    address public bob = makeAddr("bob");

    function setUp() public {
        EndpointV2Mock endpoint = new EndpointV2Mock();
        dreUSD assetImpl = new dreUSD(address(endpoint));
        ERC1967Proxy assetProxy = new ERC1967Proxy(
            address(assetImpl),
            abi.encodeWithSelector(dreUSD.initialize.selector, admin, upgrader, guardian)
        );
        asset = dreUSD(address(assetProxy));

        dreUSDs vaultImpl = new dreUSDs();
        ERC1967Proxy vProxy = new ERC1967Proxy(
            address(vaultImpl),
            abi.encodeWithSelector(dreUSDs.initialize.selector, IERC20(address(asset)), admin)
        );
        vault = dreUSDs(address(vProxy));

        dreRewardsDistributor distImpl = new dreRewardsDistributor(address(asset), address(vault));
        ERC1967Proxy dProxy = new ERC1967Proxy(
            address(distImpl),
            abi.encodeWithSelector(dreRewardsDistributor.initialize.selector, admin, admin, admin)
        );
        dist = dreRewardsDistributor(address(dProxy));

        oracle = new DreUSDOracleMock();
        expressNFT = new WithdrawalNFTMock();
        standardNFT = new WithdrawalNFTMock();
        usdc = new MockERC20("USDC", "USDC", 6);
        dreUSDManager mgrImpl = new dreUSDManager(
            address(asset), address(vault), address(usdc), address(oracle),
            address(expressNFT), address(standardNFT)
        );
        dreUSDManager.RoleAddresses memory roles = dreUSDManager.RoleAddresses({
            defaultAdmin: admin, upgrader: upgrader, moderator: moderator,
            withdrawalConfig: withdrawalConfig, pauser: pauser, keeper: keeper,
            expressOperator: expressOperator, treasury: treasury
        });
        ERC1967Proxy mProxy = new ERC1967Proxy(
            address(mgrImpl),
            abi.encodeWithSelector(
                dreUSDManager.initialize.selector, expressPayback, expressFeeRecipient, roles
            )
        );
        manager = dreUSDManager(address(mProxy));

        vm.prank(admin);
        asset.setDreUSDManager(address(manager));
        vm.prank(admin);
        vault.setRewardsDistributor(address(dist));

        bytes32 modRole = dist.MODERATOR_ROLE();
        vm.prank(admin);
        dist.grantRole(modRole, admin);

        vm.prank(address(manager));
        asset.mint(alice, 100 ether);
        vm.prank(address(manager));
        asset.mint(bob, 100 ether);
    }

    function test_PausedDistributorUnfairWithdraw() public {
        // PHASE 1: Alice + Bob deposit 50 dreUSD each
        vm.startPrank(alice);
        asset.approve(address(vault), type(uint256).max);
        uint256 aliceShares = vault.deposit(50 ether, alice);
        vm.stopPrank();

        vm.startPrank(bob);
        asset.approve(address(vault), type(uint256).max);
        uint256 bobShares = vault.deposit(50 ether, bob);
        vm.stopPrank();

        emit log_named_uint("Alice shares:", aliceShares);
        emit log_named_uint("Bob shares:  ", bobShares);
        assertEq(vault.totalSupply(), aliceShares + bobShares);

        // PHASE 2: Mint 100 dreUSD to distributor + addRewards (vest over 7 days)
        vm.prank(address(manager));
        asset.mint(address(dist), 100 ether);
        vm.prank(admin);
        dist.addRewards();
        assertEq(dist.rewards(), 100 ether, "100 dreUSD now vesting in distributor");

        // PHASE 3: Half-vest period elapses
        vm.warp(block.timestamp + 3.5 days);

        uint256 vestedHalf = dist.vestedAmount();
        emit log_named_uint("Vested after 3.5 days:", vestedHalf);
        assertApproxEqAbs(vestedHalf, 50 ether, 1 ether, "~50 dreUSD vested");

        uint256 totalAssetsHalf = vault.totalAssets();
        emit log_named_uint("totalAssets() at half-vest (pre-pause):", totalAssetsHalf);
        assertApproxEqAbs(totalAssetsHalf, 150 ether, 1 ether, "totalAssets ~= 100 + 50");

        // PHASE 4: PAUSE the DISTRIBUTOR (NOT the vault)
        vm.prank(admin);
        dist.pause();
        assertTrue(dist.paused(), "Distributor paused");
        assertFalse(vault.paused(), "Vault NOT paused - users can still withdraw");

        // KEY OBSERVATION: vestedAmount() has NO pause check
        uint256 vestedAfterPause = dist.vestedAmount();
        uint256 totalAssetsAfterPause = vault.totalAssets();
        emit log_named_uint("vestedAmount() AFTER pause (still inflated):", vestedAfterPause);
        emit log_named_uint("totalAssets() AFTER pause (still inflated):", totalAssetsAfterPause);
        assertEq(vestedAfterPause, vestedHalf, "vestedAmount unchanged by pause");
        assertEq(totalAssetsAfterPause, totalAssetsHalf, "totalAssets unchanged by pause");

        // PHASE 5: Alice redeems all 50 shares first against the inflated price
        uint256 vbBeforeAlice = vault.totalAssets() - dist.vestedAmount();
        emit log_named_uint("_virtualBalance before Alice redeem:", vbBeforeAlice);

        vm.startPrank(alice);
        uint256 aliceReceived = vault.redeem(vault.balanceOf(alice), alice, alice);
        vm.stopPrank();
        emit log_named_uint("Alice received (dreUSD):", aliceReceived);

        uint256 vbAfterAlice = vault.totalAssets() - dist.vestedAmount();
        emit log_named_uint("_virtualBalance after Alice redeem:", vbAfterAlice);

        // PHASE 6: Bob's full redeem should REVERT (underflow on _virtualBalance -= 75)
        bool bobFullRedeemReverted;
        vm.startPrank(bob);
        try vault.redeem(vault.balanceOf(bob), bob, bob) returns (uint256) {
            bobFullRedeemReverted = false;
        } catch {
            bobFullRedeemReverted = true;
        }
        vm.stopPrank();
        emit log_named_string("Bob full-redeem reverted?:", bobFullRedeemReverted ? "YES" : "NO");
        assertTrue(bobFullRedeemReverted, "Bob's full redeem should revert (underflow)");

        // PHASE 7: Search for Bob's max recoverable amount
        uint256 bobMaxRecoverable = 0;
        uint256 bobBalanceSnap = vault.balanceOf(bob);

        uint256 snapId = vm.snapshotState();
        uint256 lo = 0;
        uint256 hi = bobBalanceSnap;
        for (uint256 i = 1; i <= 50; i++) {
            uint256 trySh = (bobBalanceSnap * i) / 50;
            vm.revertToState(snapId);
            snapId = vm.snapshotState();
            vm.prank(bob);
            try vault.redeem(trySh, bob, bob) returns (uint256 got) {
                if (got > bobMaxRecoverable) {
                    bobMaxRecoverable = got;
                    lo = trySh;
                }
            } catch {
                hi = trySh;
                break;
            }
        }
        vm.revertToState(snapId);

        emit log_named_uint("Bob max recoverable (dreUSD):", bobMaxRecoverable);
        emit log_named_uint("Bob's expected fair share (dreUSD, paid in):", 50 ether);

        // PHASE 8: Assert the unfair outcome
        assertGt(aliceReceived, 50 ether, "Alice extracted MORE than she deposited");
        assertLt(bobMaxRecoverable, 50 ether,
            "Bob CANNOT even recover his original 50 dreUSD deposit");

        emit log_named_uint("Alice + Bob total recovered:", aliceReceived + bobMaxRecoverable);
        emit log_named_int(
            "Bob's net loss vs deposit (wei):",
            int256(50 ether) - int256(bobMaxRecoverable)
        );

        emit log("=== M-1 CONFIRMED: paused-distributor + un-paused-vault asymmetric pricing ===");
    }
}
```

Run with:
```
forge test --match-test test_PausedDistributorUnfairWithdraw -vv
```

Output (key values):
```
[PASS] test_PausedDistributorUnfairWithdraw()
  Alice received (dreUSD):       74999999999999999999    (~75, against a 50-deposit)
  Bob full-redeem reverted?:     YES                     (underflow on _virtualBalance -= 75)
  Bob max recoverable (dreUSD):  24000000000000000000    (~24, linear-search resolution; ceiling ~25)
  Bob's net loss vs deposit:     26000000000000000000    (52% haircut on 50-dreUSD principal)
```
````

---

## MITIGATION  (Mitigation field)

```
Apply ONE of the following — option (1) is the smallest, most local fix:

1. Gate `vestedAmount()` (or, equivalently, the call site in `totalAssets()`) on the distributor's pause state. While paused, treat vested-but-unclaimable rewards as zero so ERC-4626 pricing matches what redeemers can actually receive.

   In `dreusd/contracts/dreRewardsDistributor.sol`:
   ```solidity
   function vestedAmount() public view returns (uint256) {
       if (paused()) return 0;
       // ... existing vest math ...
   }
   ```
   OR, less invasive, in `dreusd/contracts/dreUSDs.sol#L109-L114`:
   ```solidity
   function totalAssets() public view override returns (uint256) {
       uint256 vested = rewardsDistributor.paused() ? 0 : rewardsDistributor.vestedAmount();
       return _virtualBalance + vested;
   }
   ```

2. Auto-pause the vault when the distributor is paused (and auto-pause withdrawals on the vault for the distributor-paused state). This freezes both sides symmetrically and removes the windfall-vs-lockup race entirely. Implement by overriding `maxWithdraw`/`maxRedeem` to return 0 while `rewardsDistributor.paused()` is true.

3. Make `_claimVestedRewards()` revert (rather than silently return 0) when called against a paused distributor while `totalAssets()` still reflects vested rewards. This converts the silent asymmetric drain into an explicit revert that is easier for monitoring to catch — but does NOT fix the pricing mismatch, so use only as a defence-in-depth complement to (1) or (2).

Option (1) is preferred: minimal, local, and makes ERC-4626 pricing exactly match what `_claimVestedRewards` can actually deliver, restoring the conservation invariant `sum(redeems) <= _virtualBalance` regardless of pause state.
```

---

## CHECKLIST BEFORE SUBMITTING

- [ ] Issue title matches `{actor} will {impact} {affected party}` pattern
- [ ] Code-link URLs point to the actual contest commit `6ec9cc8`
- [ ] PoC compiles and runs against the contest repo as-is with `forge test`
- [ ] Severity selection: Medium (admin action required to trigger, but causes direct loss of principal in a fully reachable path)
- [ ] Formatting renders correctly in GitHub preview before clicking Submit
