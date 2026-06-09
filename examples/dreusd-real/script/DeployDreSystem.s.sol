// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import {console} from "forge-std/console.sol";
import {Config} from "./Config.sol";
import {DeployDreUSD} from "./dreUSD/DeployDreUSD.s.sol";
import {dreUSD} from "../contracts/dreUSD.sol";
import {DeployDreUSDs} from "./dreUSDs/DeployDreUSDs.s.sol";
import {dreUSDs} from "../contracts/dreUSDs.sol";
import {dreRewardsDistributor} from "../contracts/dreRewardsDistributor.sol";
import {DeployDreRewardsDistributor} from "./rewardsDistributor/DeployDreRewardsDistributor.s.sol";
import {DeployDreUSDOracle} from "./oracle/DeployDreUSDOracle.s.sol";
import {dreUSDOracle} from "../contracts/dreUSDOracle.sol";
import {DeployDreAaveAdapter} from "./aave/DeployDreAaveAdapter.s.sol";
import {DeployWithdrawalNFT} from "./nft/DeployWithdrawalNFT.s.sol";
import {dreWithdrawalNFT} from "../contracts/dreWithdrawalNFT.sol";
import {DeployDreUSDManager} from "./dreUSDManager/DeployDreUSDManager.s.sol";
import {dreUSDManager} from "../contracts/dreUSDManager.sol";
import {DeployShareOFT} from "./ovault/deployShareOFT.s.sol";
import {DeployShareOFTAdapter} from "./ovault/deployShareOFTAdapter.s.sol";
import {dreShareOFTAdapter} from "../contracts/ovault/dreShareOFTAdapter.sol";
import {DeployComposer} from "./ovault/deployComposer.s.sol";
import {dreOVaultComposer} from "../contracts/ovault/dreOVaultComposer.sol";
import {dreShareOFT} from "../contracts/ovault/dreShareOFT.sol";
import {dreAaveAdapter} from "../contracts/dreAaveAdapter.sol";
import { SetupHelper } from "./utils/SetupHelper.s.sol";

contract DeployDreSystem is
    DeployDreUSD,
    DeployDreUSDs,
    DeployDreRewardsDistributor,
    DeployDreUSDOracle,
    DeployDreAaveAdapter,
    DeployWithdrawalNFT,
    DeployDreUSDManager,
    DeployShareOFT,
    DeployShareOFTAdapter,
    DeployComposer
{
    struct BaseComponents {
        dreUSDs vault;
        dreRewardsDistributor rewardsDistributor;
        dreAaveAdapter aaveAdapter;
        dreUSDOracle oracle;
        dreWithdrawalNFT standardNFT;
        dreWithdrawalNFT expressNFT;
        dreUSDManager manager;
        dreShareOFTAdapter shareOFTAdapter;
        dreOVaultComposer composer;
    }
    
    function run()
        external
        override(
            DeployDreUSD,
            DeployDreUSDs,
            DeployDreRewardsDistributor,
            DeployDreUSDOracle,
            DeployDreAaveAdapter,
            DeployWithdrawalNFT,
            DeployDreUSDManager,
            DeployShareOFT,
            DeployShareOFTAdapter,
            DeployComposer
        )
    {
        address endpoint = Config.getLzEndpoint(block.chainid);
        require(endpoint != address(0), "LZ_ENDPOINT_V2 not found in config");

        uint256 pk = vm.envUint("PRIVATE_KEY");
        require(pk != 0, "PRIVATE_KEY cannot be zero");

        // uint256 adminPk = vm.envUint("ADMIN_PRIVATE_KEY");
        // require(adminPk != 0, "ADMIN_PRIVATE_KEY cannot be zero");

        BaseComponents memory components;

        vm.startBroadcast(pk);

        address spokeDreUSD = address(0);
        if (block.chainid == Config.BASE_SEPOLIA || block.chainid == Config.BASE_MAINNET) {
            components = _deployHubChain(endpoint);
        } else {
            spokeDreUSD = _deploySpokeChain();
        }

        vm.stopBroadcast();

        // Keep setup in separate script
        // console.log("\n CHAIN: ", block.chainid);
        // if (block.chainid == Config.BASE_SEPOLIA || block.chainid == Config.BASE_MAINNET) {
        //     vm.startBroadcast(adminPk);
        //     SetupHelper.setupDreUSD(address(components.vault.asset()), address(components.manager), Config.getChainConfig(block.chainid).sanctionsList);
        //     SetupHelper.setupDreUSDs(address(components.vault), address(components.rewardsDistributor), address(components.shareOFTAdapter));
        //     SetupHelper.setupDreRewardsDistributor(address(components.rewardsDistributor), address(components.manager));
        //     SetupHelper.setupWithdrawalNFTs(address(components.standardNFT), address(components.expressNFT), address(components.manager));
        //     SetupHelper.setupAaveV3Adapter(address(components.aaveAdapter), address(components.manager));
        //     SetupHelper.setupDreUSDManager(address(components.manager), address(components.aaveAdapter), Config.getChainConfig(block.chainid));
        //     SetupHelper.setupDreUSDOracle(address(components.oracle), Config.getChainConfig(block.chainid));
        //     vm.stopBroadcast();
        // } else if (spokeDreUSD != address(0)) {
        //     vm.startBroadcast(adminPk);
        //     SetupHelper.setupDreUSDSpoke(spokeDreUSD, Config.getChainConfig(block.chainid).sanctionsList);
        //     vm.stopBroadcast();
        // }

        address shareOFTForVerify = block.chainid == Config.BASE_SEPOLIA || block.chainid == Config.BASE_MAINNET ? address(0) : _computeShareOFTAddress(Config.DEFAULT_CREATE2_FACTORY, Config.getChainConfig(block.chainid).defaultAdmin, spokeDreUSD);
        _verifyDeployment(components, shareOFTForVerify, spokeDreUSD);
    }

    function _deployHubChain(address endpoint) internal returns (BaseComponents memory components) {
        Config.ChainConfig memory cfg = Config.getChainConfig(block.chainid);
        address factory = Config.DEFAULT_CREATE2_FACTORY;

        dreUSD token = _deployDreUSD(endpoint, cfg.defaultAdmin, cfg.upgrader, cfg.guardian, factory);

        components = _deployBaseComponents(token, cfg);
    }

    /// @return dreUSDAddress Address of deployed dreUSD on the spoke (for setup and verify)
    function _deploySpokeChain() internal returns (address dreUSDAddress) {
        Config.ChainConfig memory cfg = Config.getChainConfig(block.chainid);
        address endpoint = Config.getLzEndpoint(block.chainid);
        address defaultAdmin = cfg.defaultAdmin;
        address factory = Config.DEFAULT_CREATE2_FACTORY;

        dreUSD token = _deployDreUSD(endpoint, defaultAdmin, cfg.upgrader, cfg.guardian, factory);
        dreUSDAddress = address(token);

        _deployShareOFT(factory, defaultAdmin, dreUSDAddress);
    }

    function _deployBaseComponents(dreUSD token, Config.ChainConfig memory cfg) internal returns (BaseComponents memory components) {
        components.vault = _deployDreUSDs(address(token), cfg.defaultAdmin);

        components.rewardsDistributor = _deployDreRewardsDistributor(
            address(token),
            address(components.vault),
            cfg.defaultAdmin,
            cfg.upgrader,
            cfg.pauser
        );

        components.oracle = _deployDreUSDOracle(cfg);

        components.standardNFT = _deployWithdrawalNFT("DRE Withdrawal", "dreWD", cfg.defaultAdmin, cfg.upgrader, address(token));
        components.expressNFT = _deployWithdrawalNFT("DRE Express Withdrawal", "dreEXP", cfg.defaultAdmin, cfg.upgrader, address(token));

        dreUSDManager.RoleAddresses memory roles = dreUSDManager.RoleAddresses({
            defaultAdmin: cfg.defaultAdmin,
            upgrader: cfg.upgrader,
            moderator: cfg.moderator,
            withdrawalConfig: cfg.withdrawalConfig,
            pauser: cfg.pauser,
            keeper: cfg.managerKeeper,
            expressOperator: cfg.managerExpressOperator,
            treasury: cfg.managerTreasury
        });
        components.manager = _deployDreUSDManager(
            address(token),
            address(components.vault),
            cfg.usdc,
            address(components.oracle),
            address(components.expressNFT),
            address(components.standardNFT),
            cfg.expressPaybackAddress,
            cfg.expressFeeRecipient,
            roles
        );

        components.aaveAdapter = _deployDreAaveAdapter(
            cfg.aaveV3Pool,
            cfg.usdc,
            cfg.aaveV3Vault,
            cfg.defaultAdmin,
            cfg.upgrader,
            address(components.manager)
        );

        components.shareOFTAdapter = _deployShareOFTAdapter(
            address(components.vault), Config.getLzEndpoint(block.chainid), cfg.defaultAdmin, cfg.stuckFundsRecipient
        );

        components.composer = _deployComposer(address(components.vault), address(token), address(components.shareOFTAdapter), cfg.stuckFundsRecipient);

        console.log("USDC address:", cfg.usdc);
        console.log("USDT address:", cfg.usdt);
    }
    
    /**
     * @notice Verifies post-deployment state: hub chains should have adapter and composer,
     *         spoke chains should have dreUSD and ShareOFT.
     * @param shareOFTAddress On spoke: ShareOFT address. On hub: address(0).
     * @param spokeDreUSDAddress On spoke: dreUSD just deployed (for ShareOFT address check). On hub: address(0).
     */
    function _verifyDeployment(BaseComponents memory components, address shareOFTAddress, address spokeDreUSDAddress) internal view {
        if (block.chainid == Config.BASE_SEPOLIA || block.chainid == Config.BASE_MAINNET) {
            _verifyHubChain(components);
        } else {
            _verifySpokeChain(components, shareOFTAddress, spokeDreUSDAddress);
        }
    }

    function _verifyHubChain(BaseComponents memory components) internal view {
        require(address(components.shareOFTAdapter) != address(0), "HUB: shareOFTAdapter must be deployed");
        require(address(components.shareOFTAdapter).code.length > 0, "HUB: shareOFTAdapter has no code");

        require(address(components.composer) != address(0), "HUB: composer must be deployed");
        require(address(components.composer).code.length > 0, "HUB: composer has no code");

        // Config.ChainConfig memory hubCfg = Config.getChainConfig(block.chainid);
        // address expectedShareOFT = _computeShareOFTAddress(Config.DEFAULT_CREATE2_FACTORY, hubCfg.defaultAdmin, hubCfg.dreUSD);
        // if (expectedShareOFT.code.length > 0) {
        //     console.log("[FAIL] ERROR: ShareOFT should NOT be deployed on hub chain!");
        //     console.log("  Found ShareOFT at:", expectedShareOFT);
        //     revert("HUB: ShareOFT must not be deployed on hub chain");
        // }
    }

    function _verifySpokeChain(BaseComponents memory components, address shareOFTAddress, address spokeDreUSDAddress) internal view {
        require(shareOFTAddress != address(0), "SPOKE: ShareOFT must be deployed");
        require(shareOFTAddress.code.length > 0, "SPOKE: ShareOFT has no code");
        require(spokeDreUSDAddress != address(0), "SPOKE: dreUSD must be deployed");

        Config.ChainConfig memory spokeCfg = Config.getChainConfig(block.chainid);
        address expectedShareOFT = _computeShareOFTAddress(Config.DEFAULT_CREATE2_FACTORY, spokeCfg.defaultAdmin, spokeDreUSDAddress);
        require(shareOFTAddress == expectedShareOFT, "SPOKE: ShareOFT address mismatch");

        require(address(components.shareOFTAdapter) == address(0), "SPOKE: shareOFTAdapter must not be deployed");
        require(address(components.composer) == address(0), "SPOKE: composer must not be deployed");
    }
}
