// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;

/// Standalone halmos test — no imports, no forge-std, no PuppyRaffle.
/// Isolates the H-3 bug line from PuppyRaffle::selectWinner:
///     totalFees = totalFees + uint64(fee);
/// Pure BitVec math; halmos handles natively.
///
/// Predicted halmos verdict: COUNTEREXAMPLE on any fee with bit 64+ set.
contract Standalone {
    function check_uint64CastDoesNotLoseFee(uint256 fee) public pure {
        if (fee >= (uint256(1) << 128)) return;     // bound search space
        uint64 truncated = uint64(fee);
        assert(uint256(truncated) == fee);
    }
}
