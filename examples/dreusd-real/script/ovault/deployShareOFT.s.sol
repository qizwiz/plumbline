// SPDX-License-Identifier: BUSL-1.1
pragma solidity 0.8.28;

import { Script, console } from "forge-std/Script.sol";
import { Create2 } from "@openzeppelin/contracts/utils/Create2.sol";
import { ERC1967Proxy } from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import { dreShareOFT } from "../../contracts/ovault/dreShareOFT.sol";
import { Config } from "../Config.sol";

/**
 * @title DeployShareOFT
 * @notice Deploys dreShareOFT on spoke chains using CREATE2 for deterministic addresses
 * @dev This OFT represents vault shares on spoke chains and should NOT be deployed on the hub chain
 * @dev Uses UUPS proxy pattern for upgradeability
 */
contract DeployShareOFT is Script {    
    // Salt for CREATE2 deployment - constant to ensure same addresses across all chains
    // For upgrades: deploy new implementation (standard CREATE) and use UpgradeShareOFT script
    bytes32 constant SHARE_OFT_SALT_IMPL = bytes32(uint256(0x9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba));
    bytes32 constant SHARE_OFT_SALT_PROXY = bytes32(uint256(0xfedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210));

    string constant NAME = "dreUSDs";
    string constant SYMBOL = "dreUSDs";

    function run() external virtual {
        Config.ChainConfig memory cfg = Config.getChainConfig(block.chainid);
        address delegate = cfg.defaultAdmin;
        require(delegate != address(0), "DEFAULT_ADMIN cannot be zero address");
        
        address factory = Config.DEFAULT_CREATE2_FACTORY;

        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        _deployShareOFT(factory, delegate);
        vm.stopBroadcast();
    }

    /// @param dreUSDAddress dreUSD (IdreUSD) address for compliance; use Config.DREUSD_ADDRESS when running standalone
    function _deployShareOFT(address factory, address delegate, address dreUSDAddress) internal returns (dreShareOFT shareOFT) {
        // Validate we're NOT on the hub chain (Base)
        require(
            block.chainid != 84532 && block.chainid != 8453,
            "ShareOFT should NOT be deployed on Base (hub chain). Use ShareOFTAdapter instead."
        );
        
        address endpoint = Config.getLzEndpoint(block.chainid);
        require(endpoint != address(0), "LZ_ENDPOINT_V2 not found in config");
        require(dreUSDAddress != address(0), "dreUSD address cannot be zero");

        address implementation = _deployShareOFTImplementation(endpoint, dreUSDAddress, factory);
        address proxyAddr = _deployShareOFTProxy(implementation, delegate, factory);
        shareOFT = dreShareOFT(proxyAddr);
    }

    /// @dev Standalone run: uses dreUSD from Config.getChainConfig(block.chainid)
    function _deployShareOFT(address factory, address delegate) internal returns (dreShareOFT shareOFT) {
        address dreUSDAddress = Config.getChainConfig(block.chainid).dreUSD;
        require(dreUSDAddress != address(0), "DREUSD_ADDRESS cannot be zero (set in chain config)");
        return _deployShareOFT(factory, delegate, dreUSDAddress);
    }

    function _deployShareOFTImplementation(address endpoint, address dreUSD, address factory) internal returns (address) {
        // Encode constructor parameters and append to creation code
        bytes memory constructorArgs = abi.encode(endpoint, dreUSD);
        bytes memory implBytecode = abi.encodePacked(
            type(dreShareOFT).creationCode,
            constructorArgs
        );
        bytes32 implBytecodeHash = keccak256(implBytecode);
        address predictedImpl = Create2.computeAddress(SHARE_OFT_SALT_IMPL, implBytecodeHash, factory);

        if (predictedImpl.code.length > 0) {
            console.log("dreShareOFT implementation already deployed at:", predictedImpl);
            return predictedImpl;
        } else {
            dreShareOFT deployedImpl = new dreShareOFT{salt: SHARE_OFT_SALT_IMPL}(endpoint, dreUSD);
            address impl = address(deployedImpl);
            require(impl == predictedImpl, "Implementation address mismatch");
            console.log("dreShareOFT implementation deployed at:", impl);
            return impl;
        }
    }

    function _deployShareOFTProxy(
        address implementation,
        address delegate,
        address factory
    ) internal returns (address) {
        require(implementation != address(0), "Implementation cannot be zero address");
        require(delegate != address(0), "Delegate cannot be zero address");
        
        bytes memory initData = abi.encodeWithSelector(
            dreShareOFT.initialize.selector,
            NAME,
            SYMBOL,
            delegate
        );
        
        // Compute CREATE2 address for proxy
        bytes memory proxyBytecode = abi.encodePacked(
            type(ERC1967Proxy).creationCode,
            abi.encode(implementation, initData)
        );
        bytes32 proxyBytecodeHash = keccak256(proxyBytecode);
        address predictedProxy = Create2.computeAddress(SHARE_OFT_SALT_PROXY, proxyBytecodeHash, factory);
        
        if (predictedProxy.code.length > 0) {
            console.log("dreShareOFT proxy already deployed at:", predictedProxy);
            return predictedProxy;
        }
        
        // Deploy proxy using CREATE2
        ERC1967Proxy proxy = new ERC1967Proxy{salt: SHARE_OFT_SALT_PROXY}(implementation, initData);
        address deployedProxy = address(proxy);
        
        require(deployedProxy == predictedProxy, "Proxy address mismatch - CREATE2 factory may not be working");
        require(deployedProxy.code.length > 0, "Proxy deployment failed - no code at address");
        
        console.log("dreShareOFT proxy deployed at:", deployedProxy);
        return deployedProxy;
    }
    
    /**
     * @notice Computes the expected ShareOFT proxy address using CREATE2
     * @dev Uses the same salt and parameters as _deployShareOFTProxy
     * @param factory The CREATE2 factory address
     * @param delegate The admin/delegate address
     * @return The computed CREATE2 address for ShareOFT proxy
     */
    /// @param dreUSDAddress dreUSD address used in ShareOFT constructor (for CREATE2 address computation)
    function _computeShareOFTAddress(address factory, address delegate, address dreUSDAddress) internal view returns (address) {
        address endpoint = Config.getLzEndpoint(block.chainid);
        require(dreUSDAddress != address(0), "dreUSD cannot be zero for address computation");

        bytes memory constructorArgs = abi.encode(endpoint, dreUSDAddress);
        bytes memory implBytecode = abi.encodePacked(
            type(dreShareOFT).creationCode,
            constructorArgs
        );
        bytes32 implBytecodeHash = keccak256(implBytecode);
        address implementation = Create2.computeAddress(SHARE_OFT_SALT_IMPL, implBytecodeHash, factory);
        
        // Then compute proxy address
        bytes memory initData = abi.encodeWithSelector(
            dreShareOFT.initialize.selector,
            NAME,
            SYMBOL,
            delegate
        );
        bytes memory proxyBytecode = abi.encodePacked(
            type(ERC1967Proxy).creationCode,
            abi.encode(implementation, initData)
        );
        bytes32 proxyBytecodeHash = keccak256(proxyBytecode);
        
        return Create2.computeAddress(SHARE_OFT_SALT_PROXY, proxyBytecodeHash, factory);
    }

    function _computeShareOFTAddress(address factory, address delegate) internal view returns (address) {
        return _computeShareOFTAddress(factory, delegate, Config.getChainConfig(block.chainid).dreUSD);
    }
}
