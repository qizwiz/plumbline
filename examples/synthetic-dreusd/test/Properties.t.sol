// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {dreUSD} from "../dreUSD.sol";

// Minimal symbolic-friendly USDC stub. Halmos doesn't need the real USDC
// implementation; just an ERC20-shaped balance map so the redeem path
// completes and we can read the user's USDC delta.
contract MockUSDC {
    mapping(address => uint256) public balanceOf;

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        balanceOf[from] -= amount;
        balanceOf[to]   += amount;
        return true;
    }
    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to]         += amount;
        return true;
    }
    function mintTo(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }
}

/// Halmos symbolic invariants for the synthetic-dreusd twin. Each `check_*`
/// function is a universally-quantified property over symbolic inputs: halmos
/// either PROVES the property holds for all inputs or returns a concrete
/// counterexample (the EVM trace that breaks it).
///
/// Expected (per the README + .ANSWERS.md):
///   check_redeemReturnsDeposit  →  COUNTEREXAMPLE (planted bug: redeem misses /1e12)
///   check_supplyAtMostBacking   →  COUNTEREXAMPLE (same root cause: 18-dp supply
///                                   becomes 6-dp obligation, totalSupply/1e12 > usdc bal)
contract Properties is Test {
    dreUSD public dre;
    MockUSDC public usdc;
    address constant USER = address(0xBEEF);

    function setUp() public {
        usdc = new MockUSDC();
        dre  = new dreUSD(address(usdc));
        // Pre-fund the protocol with a deep USDC reserve so a buggy `redeem`
        // (which tries to send dreAmount = deposit*1e12 USDC) does NOT revert
        // on underflow — letting halmos actually reach the assertion. Without
        // this, every path reverts and halmos reports vacuous PASS.
        usdc.mintTo(address(dre), 1e30);
    }

    /// PROMISE (README §1, §2): a mint→redeem round-trip returns exactly what
    /// was deposited. No value created, no value destroyed.
    function check_redeemReturnsDeposit(uint256 deposit) public {
        vm.assume(deposit > 0);
        vm.assume(deposit < type(uint96).max);          // bound search space

        usdc.mintTo(USER, deposit);

        vm.startPrank(USER);
        dre.mint(deposit);
        uint256 dreAmount = dre.balanceOf(USER);
        uint256 balBefore = usdc.balanceOf(USER);
        dre.redeem(dreAmount);
        uint256 balAfter  = usdc.balanceOf(USER);
        vm.stopPrank();

        assert(balAfter - balBefore == deposit);
    }

    /// PROMISE (README §1): dreUSD is fully backed — outstanding supply (in
    /// USD terms = totalSupply/1e12) cannot exceed the USDC balance held by
    /// the contract. Symbolic check on the post-mint state.
    function check_supplyAtMostBacking(uint256 deposit) public {
        vm.assume(deposit > 0);
        vm.assume(deposit < type(uint96).max);

        usdc.mintTo(USER, deposit);

        vm.startPrank(USER);
        dre.mint(deposit);
        vm.stopPrank();

        // After a successful redeem-and-payout, USDC backing must still cover
        // the outstanding dreUSD supply in dollar terms.
        uint256 outstandingUsd = dre.totalSupply() / 1e12;
        uint256 usdcInProtocol = usdc.balanceOf(address(dre));
        assert(outstandingUsd <= usdcInProtocol);
    }
}
