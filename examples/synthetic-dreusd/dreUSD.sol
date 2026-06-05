// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC20} from "solmate/tokens/ERC20.sol";

interface IUSDC {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

/// @title  dreUSD — USD-pegged stablecoin, fully backed by USDC.
/// @notice Every dreUSD is backed one-to-one by USDC held in the protocol. Mint $X of USDC to receive
///         X dreUSD; redeem X dreUSD to receive back $X of USDC. The peg holds in both directions and
///         no value is created or destroyed by a mint/redeem round-trip.
contract dreUSD is ERC20 {
    IUSDC public immutable usdc;
    address public minter;

    constructor(address _usdc) ERC20("dre USD", "dreUSD", 18) {
        usdc = IUSDC(_usdc);
        minter = msg.sender;
    }

    /// @notice Mint dreUSD by depositing USDC at one dollar to one dreUSD.
    function mint(uint256 usdcAmount) external {
        usdc.transferFrom(msg.sender, address(this), usdcAmount);
        _mint(msg.sender, usdcAmount * 1e12);
    }

    /// @notice Redeem dreUSD back into the underlying USDC at one dreUSD to one dollar.
    function redeem(uint256 dreAmount) external {
        _burn(msg.sender, dreAmount);
        usdc.transfer(msg.sender, dreAmount);
    }
}
