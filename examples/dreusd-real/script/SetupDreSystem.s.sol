// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";
import { Config } from "./Config.sol";
import { SetupHelper } from "./utils/SetupHelper.s.sol";
import { IAaveV3Adapter } from "../contracts/interfaces/IAaveV3Adapter.sol";
import { IdreUSDManager } from "../contracts/interfaces/IdreUSDManager.sol";
import { MockERC20 } from "../contracts/mocks/MockERC20.sol";
import { MessageHashUtils } from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/**
 * @title SetupDreSystem
 * @notice Post-deployment setup: roles and contract references.
 *        All addresses must be set in Config.sol before running.
 *        Uses ADMIN_PRIVATE_KEY for admin operations.
 *        TODO: Rewards funding: transfer dreUSD into dreRewardsDistributor, then call addRewards(); no approvals needed.
 */
contract SetupDreSystem is Script {
    function run() external {
        uint256 adminPk = vm.envUint("ADMIN_PRIVATE_KEY");
        require(adminPk != 0, "ADMIN_PRIVATE_KEY cannot be zero");
        require(block.chainid == Config.BASE_SEPOLIA || block.chainid == Config.BASE_MAINNET, "SetupDreSystem only on Base Sepolia or Base Mainnet");

        Config.ChainConfig memory cfg = Config.getChainConfig(block.chainid);

        vm.startBroadcast(adminPk);
        SetupHelper.setupDreUSD(cfg.dreUSD, cfg.manager, cfg.sanctionsList);
        SetupHelper.setupDreUSDs(cfg.dreUSDs, cfg.rewardsDistributor, cfg.dreShareOFTAdapter);
        SetupHelper.setupDreRewardsDistributor(cfg.rewardsDistributor, cfg.manager);
        SetupHelper.setupWithdrawalNFTs(cfg.withdrawalNFT, cfg.expressWithdrawalNFT, cfg.manager);
        SetupHelper.setupAaveV3Adapter(cfg.aaveV3Adapter, cfg.manager);
        SetupHelper.setupDreUSDManager(cfg.manager, cfg.aaveV3Adapter, cfg);
        SetupHelper.setupDreUSDOracle(cfg.oracle, cfg);
        SetupHelper.checkSetup(cfg.dreUSD, cfg.dreUSDs, cfg.manager, cfg.rewardsDistributor, cfg.withdrawalNFT, cfg.expressWithdrawalNFT, cfg.aaveV3Adapter, cfg.oracle, cfg);
        _postDeploySepolia(adminPk, cfg);
        vm.stopBroadcast();
    }

    function _postDeploySepolia(uint256 custodianPk, Config.ChainConfig memory cfg) internal {
        if (block.chainid != Config.BASE_SEPOLIA) return;

        address user = 0xDD6Ac361124b91eBccf29EA28B08d0d0CF073726;
        address usdc = cfg.usdc;
        address aUSDC = IAaveV3Adapter(cfg.aaveV3Adapter).getAToken();
        address rewardsDistributor = cfg.rewardsDistributor;

        MockERC20(usdc).mint(user, 100_000_000e6);

        bytes32 ethSignedHash = MessageHashUtils.toEthSignedMessageHash(keccak256(
            abi.encode(keccak256(abi.encodePacked("mint-ref1")), rewardsDistributor, 1000_00, block.timestamp + 1 hours, block.chainid, cfg.manager)
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(custodianPk, ethSignedHash);
        bytes memory custodianSig = abi.encodePacked(r, s, v);
        IdreUSDManager(cfg.manager).mintRewards(
            IdreUSDManager.FiatMint(keccak256(abi.encodePacked("mint-ref1")), rewardsDistributor, 1000_00, block.timestamp + 1 hours, block.chainid),
            custodianSig
        );

        MockERC20(aUSDC).mint(IAaveV3Adapter(cfg.aaveV3Adapter).getVault(), 1_000_000e6);
        MockERC20(aUSDC).approve(address(cfg.aaveV3Adapter), type(uint256).max);
        MockERC20(usdc).mint(aUSDC, 1_000_000e6);

        console.log("Rewards distributor balance:", MockERC20(cfg.dreUSD).balanceOf(cfg.rewardsDistributor));
        console.log("Aave adapter allowence on vault to spend aUSDC:", MockERC20(aUSDC).allowance(IAaveV3Adapter(cfg.aaveV3Adapter).getVault(), cfg.aaveV3Adapter));
    }
}
