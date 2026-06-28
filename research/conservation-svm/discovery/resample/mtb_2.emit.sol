// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {StakingRewards} from "../src/StakingRewards.sol";

interface Vm { function assume(bool) external; }

contract DiscoveredTest {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    StakingRewards staking;

    function setUp() public {
        staking = new StakingRewards();
        // Initialize with this contract as both distribution and owner.
        // staking token == address(0) so safeTransfer/From are no-ops avoided by symbolic exec
        staking.initialize(address(this), address(0), address(this), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        // Bound symbolic amounts to avoid overflow noise in the arithmetic
        vm.assume(a > 0 && a < type(uint128).max);
        vm.assume(b > 0 && b <= a); // can only withdraw what is staked

        // --- stake: aggregate and holding must move together ---
        uint256 aggBeforeStake = staking.totalSupply();
        uint256 holdBeforeStake = staking.balanceOf(address(this));

        staking.stakeFor(address(this), a);

        uint256 aggAfterStake = staking.totalSupply();
        uint256 holdAfterStake = staking.balanceOf(address(this));

        int256 aggDeltaStake = int256(aggAfterStake) - int256(aggBeforeStake);
        int256 holdDeltaStake = int256(holdAfterStake) - int256(holdBeforeStake);
        assert(aggDeltaStake == holdDeltaStake);

        // --- withdraw: aggregate and holding must move together ---
        uint256 aggBeforeW = staking.totalSupply();
        uint256 holdBeforeW = staking.balanceOf(address(this));

        staking.withdraw(b);

        uint256 aggAfterW = staking.totalSupply();
        uint256 holdAfterW = staking.balanceOf(address(this));

        int256 aggDeltaW = int256(aggAfterW) - int256(aggBeforeW);
        int256 holdDeltaW = int256(holdAfterW) - int256(holdBeforeW);
        assert(aggDeltaW == holdDeltaW);
    }
}