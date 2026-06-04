// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC20} from "solmate/tokens/ERC20.sol";

interface IUSDC {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

/// @title  dreUSD — USD-pegged stablecoin, 1:1 USDC-backed.
/// @notice Every dreUSD is backed 1:1 by USDC held by the protocol. Mint $X of USDC -> X dreUSD;
///         redeeming X dreUSD returns exactly $X of USDC. No value is created or destroyed.
/// @dev    PLANTED BUG (decimals 6<->18). USDC is 6 decimals, dreUSD is 18. `mint` scales correctly
///         (×1e12); `redeem` does NOT scale back (÷1e12), so it pays out 1e12× too much USDC per
///         dreUSD — letting an attacker drain other users' backing and breaking 1:1 redeem.
contract dreUSD is ERC20 {
    IUSDC public immutable usdc; // 6 decimals
    address public minter;

    constructor(address _usdc) ERC20("dre USD", "dreUSD", 18) {
        usdc = IUSDC(_usdc);
        minter = msg.sender;
    }

    /// @notice Mint dreUSD by depositing USDC at $1 = 1 dreUSD.
    function mint(uint256 usdcAmount) external {            // usdcAmount: 6-decimal USDC units
        usdc.transferFrom(msg.sender, address(this), usdcAmount);
        _mint(msg.sender, usdcAmount * 1e12);              // correct: scale 6 -> 18 decimals
    }

    /// @notice Redeem dreUSD back to USDC at $1 = 1 dreUSD.
    function redeem(uint256 dreAmount) external {           // dreAmount: 18-decimal dreUSD units
        _burn(msg.sender, dreAmount);
        usdc.transfer(msg.sender, dreAmount);              // BUG: missing /1e12 -> pays 1e12x too much
    }
}
