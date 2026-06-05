// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC4626} from "solmate/tokens/ERC4626.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";

/// @title  dreUSDs — staked dreUSD. Real yield, paid daily.
/// @notice Stake dreUSD to earn the protocol's daily real-estate-credit yield. Yield accrues to
///         stakers in proportion to their stake and the time they remain staked; depositors are
///         rewarded for committing capital, not for being present at the moment of distribution.
contract dreUSDs is ERC4626 {
    address public keeper;

    constructor(ERC20 _dreUSD) ERC4626(_dreUSD, "Staked dreUSD", "dreUSDs") {
        keeper = msg.sender;
    }

    /// @notice Total dreUSD backing the outstanding shares.
    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }

    /// @notice Pay the day's yield into the vault for distribution to stakers.
    /// @param amount The dreUSD yield to distribute for the period.
    function distributeYield(uint256 amount) external {
        require(msg.sender == keeper, "only keeper");
        asset.transferFrom(msg.sender, address(this), amount);
    }
}
