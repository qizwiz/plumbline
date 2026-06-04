// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC4626} from "solmate/tokens/ERC4626.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";

/// @title  dreUSDs — staked dreUSD, "REAL YIELD. PAID DAILY."
/// @notice Stake dreUSD to earn the daily real-estate-credit yield. Yield is distributed FAIRLY to
///         stakers in proportion to their time-weighted stake — a just-in-time depositor cannot
///         capture yield they did not earn, and long-term stakers are never diluted by JIT capital.
/// @dev    PLANTED BUG (JIT yield sniping). The @notice above is the PROMISE; the code violates it.
contract dreUSDs is ERC4626 {
    address public keeper;

    constructor(ERC20 _dreUSD) ERC4626(_dreUSD, "Staked dreUSD", "dreUSDs", 18) {
        keeper = msg.sender;
    }

    /// @notice Assets backing the shares.
    /// @dev    BUG: returns the raw balance with NO unvested-yield subtraction. A lump distribution
    ///         therefore raises share price in a single transaction -> instantly snipeable.
    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }

    /// @notice Keeper pays in the daily yield, distributed to stakers.
    /// @dev    BUG (JIT): yield arrives as an INSTANT LUMP — `totalAssets()` jumps this block, so
    ///         price-per-share jumps this block. Combined with no withdrawal cooldown (deposit and
    ///         redeem are allowed in the same block), an attacker sandwiches this call: deposit a large
    ///         amount immediately before, redeem immediately after, and walks away with a pro-rata
    ///         slice of yield that the long-term stakers actually earned.
    ///         The faithful design STREAMS/vests the yield over the day (see Ethena sUSDe
    ///         `transferInRewards` + `getUnvestedAmount`); this contract does not.
    function distributeYield(uint256 amount) external {
        require(msg.sender == keeper, "only keeper");
        asset.transferFrom(msg.sender, address(this), amount); // instant lump -> JIT-snipeable
    }

    // NOTE (planted): there is intentionally NO withdrawal cooldown / lockup, so deposit-then-redeem
    // in the same block is permitted — the other half of what makes the JIT sandwich possible.
}
