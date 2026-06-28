// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;

import {StakingRewards} from "../src/StakingRewards.sol";

interface Vm { function assume(bool) external; }

contract DiscoveredTest {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    StakingRewards staking;

    function setUp() public {
        staking = new StakingRewards();
        // initialize with shouldTransfer=false so token transfers are no-ops we don't need to model
        staking.initialize(address(this), address(0xBEEF), address(0xCAFE), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        // bound symbolic inputs to avoid spurious overflow / underflow noise
        vm.assume(a > 0 && a < 1e30);
        vm.assume(b > 0 && b <= a); // can only withdraw up to staked

        // snapshot aggregate and individual holding before
        uint256 aggBefore = staking.totalSupply();
        uint256 balBefore = staking.balanceOf(address(this));

        // exercise state-changing functions with symbolic amounts.
        // NOTE: real transfers are skipped (shouldTransfer / staking token are stubs);
        // we only assert the internal-accounting conservation law.
        staking.stake(a);
        staking.withdraw(b);

        uint256 aggAfter = staking.totalSupply();
        uint256 balAfter = staking.balanceOf(address(this));

        int256 aggDelta = int256(aggAfter) - int256(aggBefore);
        int256 holdingDelta = int256(balAfter) - int256(balBefore);

        // induced invariant: aggregate moves in lockstep with the holding it accounts for
        assert(aggDelta == holdingDelta);
    }
}