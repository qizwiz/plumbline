// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {StakerBitmap} from "../src/StakerBitmap.sol";

/// THE GATE: a staker whose single bit is set in the bitmap MUST be recovered by
/// getStakersFromBitmap — otherwise slash() can never punish them. We let halmos
/// pick the staker index k symbolically over the full valid range [1, 255].
/// Expectation: counterexample at k = 255 (the loop's `i < 255` skips bit 255),
/// proving the 255th staker is invisible to slashing.
contract BitmapTest is Test {
    StakerBitmap s;

    function setUp() public {
        s = new StakerBitmap();
        s.fill();
    }

    function check_everyStakerRecoverable(uint8 k) public view {
        vm.assume(k >= 1 && k <= 255);
        uint256 bitmap = uint256(1) << uint256(k);
        address[] memory got = s.getStakersFromBitmap(bitmap);
        // the staker registered in slot k-1 is address(k); slash() must see it
        assert(got.length == 1);
        assert(got[0] == address(uint160(uint256(k))));
    }

    // concrete deterministic confirmation: a normal staker (index 254) is recovered...
    function test_staker254_recovered() public view {
        address[] memory got = s.getStakersFromBitmap(uint256(1) << 254);
        assertEq(got[0], address(uint160(254)), "254 should be recovered");
    }

    // ...but the 255th staker (index 255) is NOT — slash() can never see them.
    function test_staker255_recovered() public view {
        address[] memory got = s.getStakersFromBitmap(uint256(1) << 255);
        assertEq(got[0], address(uint160(255)), "255 should be recovered");
    }
}
