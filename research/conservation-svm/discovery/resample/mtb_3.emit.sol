// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface Vm { function assume(bool) external; }

import {StakingRewards} from "../src/StakingRewards.sol";

contract DiscoveredTest {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    StakingRewards staking;

    function setUp() public {
        staking = new StakingRewards();
        // shouldTransfer=false to avoid external token transfer dependence;
        // deployer is rewardsDistribution and owner so stakeFor is callable.
        staking.initialize(address(this), address(this), address(this), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        // bound inputs to avoid overflow / token-transfer reverts
        vm.assume(a > 0 && a < 1e30);
        vm.assume(b > 0 && b <= a);

        address user = address(this);

        // snapshot aggregate and holding before mutations
        uint256 aggBefore = staking.totalSupply();
        uint256 holdBefore = staking.balanceOf(user);

        // exercise state-changing functions with symbolic amounts.
        // stakeFor increases both aggregate and holding (a)
        // withdraw decreases both aggregate and holding (b)
        staking.stakeFor(user, a);
        staking.withdraw(b);

        uint256 aggAfter = staking.totalSupply();
        uint256 holdAfter = staking.balanceOf(user);

        int256 aggDelta = int256(aggAfter) - int256(aggBefore);
        int256 holdDelta = int256(holdAfter) - int256(holdBefore);

        // induced invariant: aggregate delta must equal the holding delta
        assert(aggDelta == holdDelta);
    }
}