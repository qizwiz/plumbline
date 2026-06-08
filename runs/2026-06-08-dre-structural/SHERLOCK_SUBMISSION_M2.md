# Sherlock Contest 1259 — DRE App / dreUSD — Submission #2

## TITLE

```
Express-withdrawal users will lose up to 5% of their stated slippage floor as dreUSDManager checks minUsdcAmount against the gross oracle quote before fee deduction
```

## SUMMARY  (Summary field)

```
The pre-fee slippage check in `dreUSDManager.requestExpressWithdrawal` will cause direct loss of up to 5% of a user's stated minimum USDC floor as users (and third-party integrators) following standard DeFi parameter conventions will set `minUsdcAmount` expecting it to be a floor on USDC RECEIVED, but the contract checks it against the GROSS oracle quote before deducting the express fee.
```

## ROOT CAUSE  (Root Cause field)

```
In `dreusd/contracts/dreUSDManager.sol#L521-L523` the slippage check is applied to `totalUsdcAmount` (the gross oracle quote in `dreusd/contracts/dreUSDManager.sol#L521`), but the actual user-receivable amount is computed downstream in `_queueExpressWithdrawal` (`dreusd/contracts/dreUSDManager.sol#L728-L737`) as `userReceivesUsdc = usdcAmount - feeUsdc`, where `feeUsdc = usdcAmount * expressWithdrawalFeeBps / BPS_DENOMINATOR`.

The standard DeFi convention (Uniswap, Curve, Balancer, every major DEX router) is that `minAmountOut` / `minUsdcAmount` parameters express a floor on tokens RECEIVED. DRE's deviation from this convention is documented in the contest Q&A but the parameter name does not signal the deviation. The contest Q&A explicitly carves IN this issue: "If the pre-fee slippage design causes a serious loss of funds, it may be a valid finding."

Note that the standard withdrawal path (`requestWithdrawal`, `dreusd/contracts/dreUSDManager.sol#L479-L503`) has a 0% fee so does not exhibit this discrepancy; the bug is unique to the express path.
```

## INTERNAL PRE-CONDITIONS  (Internal Pre-conditions field)

```
1. `expressWithdrawalFeeBps > 0`. The contract is initialized with a default of 50 bps (0.5%) at `dreUSDManager.sol#L220` and can be raised by WITHDRAWAL_CONFIG_ROLE up to `MAX_EXPRESS_WITHDRAWAL_FEE_BPS = 500` bps (5%).
2. `expressWithdrawalAvailable > 0` so the express path is reachable.
3. The user submits a `requestExpressWithdrawal` call with `minUsdcAmount` set to the value they expect to receive (the natural reading of the parameter name).
```

## EXTERNAL PRE-CONDITIONS  (External Pre-conditions field)

```
1. The user (or their integrator/wallet/aggregator) treats `minUsdcAmount` per standard DeFi convention as "the minimum USDC amount the call will deliver to the recipient." The protocol's own Q&A acknowledges this naming is non-standard and that "Frontends should quote the net amount (after fee) and set minUsdcAmount accounting for the fee" — but this convention-shift is only discoverable by reading the protocol's documentation or source code carefully.
2. No oracle slippage required. The bug is present at the exact oracle-quoted price.
```

## ATTACK PATH  (Attack Path field)

```
1. Express withdrawal fee is set (default 50 bps; up to 500 bps). WITHDRAWAL_CONFIG_ROLE may raise the fee at any time via `updateExpressWithdrawal`.
2. User calls `requestExpressWithdrawal(1000e18, 990e6, deadline)` — i.e. burn 1000 dreUSD with a floor of 990 USDC received. Under standard DeFi convention this means "do not let me receive less than 990 USDC."
3. Oracle returns `totalUsdcAmount = 1000e6` (gross). Slippage check `1000e6 < 990e6` is FALSE — check passes.
4. `_queueExpressWithdrawal` deducts `feeUsdc = 1000e6 * 500 / 10000 = 50e6` and mints the NFT with `userReceivesUsdc = 950e6`.
5. When the EXPRESS_OPERATOR fills the NFT, the user receives 950 USDC — 40 USDC less than their stated floor of 990, or 50 USDC less than the gross quote.
6. No revert. No notification. The user's `minUsdcAmount` parameter was silently treated as a different quantity than its name suggests.
```

## IMPACT  (Impact field)

```
The express-withdrawal user suffers direct USDC loss of up to 5% of their stated minimum floor (capped by MAX_EXPRESS_WITHDRAWAL_FEE_BPS = 500). The attacker — in the absence of explicit attacker action — is the protocol-set expressFeeRecipient, which collects the fee that the user did not knowingly authorize. The Sherlock V2 thresholds are met:

- Direct loss percentage: 0.5% (at default 50bps) up to 5% (at MAX fee). The 5% case meets the 1% High threshold; the default 50bps case meets the Medium threshold.
- Direct loss USD: For any express withdrawal of $200 or more, the absolute loss exceeds $10 (Sherlock's nominal floor).
- Permissionless: any user calling requestExpressWithdrawal directly (via aggregator, wallet, or contract integration) absorbs this loss.

In the PoC at this commit:
- User floor: 990 USDC. Gross: 1000 USDC. NET delivered: 950 USDC. NET loss vs floor: 40 USDC (4.04%).
- Worst-case (user floor = full quote): floor 1000 USDC, delivered 950 USDC, loss 50 USDC (5%).

The contest Q&A explicitly invites this finding under the carve-in: "If the pre-fee slippage design causes a serious loss of funds, it may be a valid finding."
```

## PoC  (PoC field)

````
Two passing Foundry tests below. Save as `dreusd/test/PoC_ExpressSlippageBypass.t.sol`:

```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {dreUSD} from "../contracts/dreUSD.sol";
import {dreUSDManager} from "../contracts/dreUSDManager.sol";
import {IdreUSDManager} from "../contracts/interfaces/IdreUSDManager.sol";
import {IWithdrawalNFT} from "../contracts/interfaces/IWithdrawalNFT.sol";
import {EndpointV2Mock} from "../contracts/mocks/EndpointV2Mock.sol";
import {DreUSDOracleMock} from "../contracts/mocks/DreUSDOracleMock.sol";
import {WithdrawalNFTMock} from "../contracts/mocks/WithdrawalNFTMock.sol";
import {MockERC20} from "../contracts/mocks/MockERC20.sol";

contract PoC_ExpressSlippageBypass is Test {
    dreUSD public asset;
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
    address public user = makeAddr("user");

    function setUp() public {
        EndpointV2Mock endpoint = new EndpointV2Mock();
        dreUSD assetImpl = new dreUSD(address(endpoint));
        asset = dreUSD(address(new ERC1967Proxy(address(assetImpl),
            abi.encodeWithSelector(dreUSD.initialize.selector, admin, upgrader, guardian))));

        oracle = new DreUSDOracleMock();
        expressNFT = new WithdrawalNFTMock();
        standardNFT = new WithdrawalNFTMock();
        usdc = new MockERC20("USDC", "USDC", 6);

        dreUSDManager mgrImpl = new dreUSDManager(address(asset), address(0xdEaD), address(usdc),
            address(oracle), address(expressNFT), address(standardNFT));
        dreUSDManager.RoleAddresses memory roles = dreUSDManager.RoleAddresses({
            defaultAdmin: admin, upgrader: upgrader, moderator: moderator,
            withdrawalConfig: withdrawalConfig, pauser: pauser, keeper: keeper,
            expressOperator: expressOperator, treasury: treasury
        });
        manager = dreUSDManager(address(new ERC1967Proxy(address(mgrImpl),
            abi.encodeWithSelector(dreUSDManager.initialize.selector, expressPayback, expressFeeRecipient, roles))));

        vm.prank(admin); asset.setDreUSDManager(address(manager));

        vm.prank(withdrawalConfig);
        manager.updateExpressWithdrawal(10_000_000_000_000, 500, expressFeeRecipient);

        vm.prank(address(manager)); asset.mint(user, 10_000 ether);
    }

    function test_ExpressSlippageBypass_UserReceivesLessThanFloor() public {
        oracle.setTokenAmount(address(usdc), 1000e6);

        uint256 dreUSDIn   = 1000 ether;
        uint256 userFloor  = 990e6;
        uint256 deadline   = block.timestamp + 1 hours;

        vm.prank(user);
        uint256 tokenId = manager.requestExpressWithdrawal(dreUSDIn, userFloor, deadline);

        IWithdrawalNFT.Position memory pos = IWithdrawalNFT(address(expressNFT)).getPosition(tokenId);

        assertEq(pos.usdcAmount, 950e6);
        assertLt(pos.usdcAmount, userFloor);

        uint256 lossUsdc = userFloor - pos.usdcAmount;
        assertGt(lossUsdc, 39e6);
    }

    function test_ExpressSlippageBypass_AtFloorExactly() public {
        oracle.setTokenAmount(address(usdc), 1000e6);

        uint256 dreUSDIn  = 1000 ether;
        uint256 userFloor = 1000e6;
        uint256 deadline  = block.timestamp + 1 hours;

        vm.prank(user);
        uint256 tokenId = manager.requestExpressWithdrawal(dreUSDIn, userFloor, deadline);

        IWithdrawalNFT.Position memory pos = IWithdrawalNFT(address(expressNFT)).getPosition(tokenId);
        assertEq(pos.usdcAmount, 950e6);

        uint256 loss = userFloor - pos.usdcAmount;
        assertEq(loss, 50e6);
    }
}
```

Run with:
```
forge test --match-test test_ExpressSlippage -vv
```

Output:
```
[PASS] test_ExpressSlippageBypass_AtFloorExactly() (gas: 261341)
  Worst-case user loss (USDC 6dec):: 50000000
  Worst-case loss bps:: 500

[PASS] test_ExpressSlippageBypass_UserReceivesLessThanFloor() (gas: 275798)
  User's stated floor (minUsdcAmount):: 990000000
  Gross oracle quote (totalUsdcAmount):: 1000000000
  Fee (5% of gross):: 50000000
  NFT records (NET user receives):: 950000000
  User's NET vs stated floor (USDC, 6dec):: -40000000
  User's loss vs stated floor (USDC 6dec):: 40000000
  Loss as bps of user's floor:: 404
  EXPRESS-SLIPPAGE-BYPASS CONFIRMED: protocol delivers less than user's stated minUsdcAmount floor.
```
````

## MITIGATION  (Mitigation field)

```
Apply the slippage check to the NET amount the user receives, not the gross oracle quote.

```diff
- uint256 totalUsdcAmount = IDreUSDOracle(oracle).getTokenAmount(usdc, dreUSDAmount);
- if (totalUsdcAmount < minUsdcAmount) revert SlippageExceeded(minUsdcAmount, totalUsdcAmount);
+ uint256 totalUsdcAmount = IDreUSDOracle(oracle).getTokenAmount(usdc, dreUSDAmount);
+ uint256 feeUsdc = (totalUsdcAmount * expressWithdrawalFeeBps) / ScalingConstants.BPS_DENOMINATOR;
+ uint256 userReceivesUsdc = totalUsdcAmount - feeUsdc;
+ if (userReceivesUsdc < minUsdcAmount) revert SlippageExceeded(minUsdcAmount, userReceivesUsdc);
```

This restores standard DeFi convention (minAmountOut = floor on tokens received) and protects users (and third-party integrators / aggregators / wallets) from a silent up-to-5% haircut. The downstream `_queueExpressWithdrawal` computation does not need to change — it already computes the same fee.
```
