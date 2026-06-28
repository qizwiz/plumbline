// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface Vm { function assume(bool) external; }
Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

import {StakingRewards} from "../src/StakingRewards.sol";

contract DiscoveredTest {
    StakingRewards sr;

    function setUp() public {
        sr = new StakingRewards();
        // initialize so the contract is usable; staking token / rewards token can be self/dummy
        sr.initialize(address(this), address(this), address(this), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        // bound symbolic inputs to avoid overflow / unrelated reverts
        vm.assume(a > 0 && a < 1e30);
        vm.assume(b > 0 && b <= a);

        address user = address(this);

        // snapshot aggregate and holding before
        uint256 aggBefore = sr.totalSupply();
        uint256 balBefore = sr.balanceOf(user);

        // exercise state-changing functions with symbolic amounts.
        // stakeFor is callable since msg.sender == rewardsDistribution (this)
        sr.stakeFor(user, a);
        sr.withdraw(b);

        uint256 aggAfter = sr.totalSupply();
        uint256 balAfter = sr.balanceOf(user);

        int256 aggDelta = int256(aggAfter) - int256(aggBefore);
        int256 balDelta = int256(balAfter) - int256(balBefore);

        // induced conservation invariant: aggregate delta must equal holding delta
        assert(aggDelta == balDelta);
    }
}