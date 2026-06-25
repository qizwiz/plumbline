// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface Vm { function assume(bool) external; }

import {Vault} from "../src/Vault.sol";

contract DiscoveredTest {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    Vault vault;

    function setUp() public {
        vault = new Vault();
    }

    function check_invariant(uint256 a, uint256 b) public {
        // Bound inputs to avoid trivial overflow/underflow reverts
        vm.assume(a < type(uint128).max);
        vm.assume(b <= a);

        // enter: increase holding and aggregate
        uint256 aggBefore1 = vault.g_totalAssets();
        uint256 holdBefore1 = vault.userShares(address(this));
        vault.enter(a);
        uint256 aggAfter1 = vault.g_totalAssets();
        uint256 holdAfter1 = vault.userShares(address(this));

        int256 aggDelta1 = int256(aggAfter1) - int256(aggBefore1);
        int256 holdDelta1 = int256(holdAfter1) - int256(holdBefore1);
        assert(aggDelta1 == holdDelta1);

        // exit: decrease holding and aggregate
        uint256 aggBefore2 = vault.g_totalAssets();
        uint256 holdBefore2 = vault.userShares(address(this));
        vault.exit(b);
        uint256 aggAfter2 = vault.g_totalAssets();
        uint256 holdAfter2 = vault.userShares(address(this));

        int256 aggDelta2 = int256(aggAfter2) - int256(aggBefore2);
        int256 holdDelta2 = int256(holdAfter2) - int256(holdBefore2);
        assert(aggDelta2 == holdDelta2);
    }
}