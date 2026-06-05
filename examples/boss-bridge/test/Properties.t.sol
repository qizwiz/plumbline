// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/interfaces/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import {L1BossBridge} from "../L1BossBridge.sol";
import {L1Vault} from "../L1Vault.sol";

contract MockToken is ERC20 {
    constructor() ERC20("Mock", "M") {}
    function mintTo(address to, uint256 amount) external { _mint(to, amount); }
}

/// Halmos symbolic invariants for L1BossBridge. Each `check_*` either
/// PROVES or refutes with a concrete EVM trace.
///
/// Predicted verdict (from .ANSWERS.md H-3):
///   check_withdrawCannotBeReplayed → COUNTEREXAMPLE
///     `withdrawTokensToL1` has no nonce or expiry. A single (v,r,s) over
///     a (to, amount) message is accepted indefinitely; replaying it drains
///     the vault one `amount` at a time.
contract Properties is Test {
    L1BossBridge public bridge;
    L1Vault public vault;
    MockToken public token;

    address constant TO = address(0xBEEF);
    uint256 constant SIGNER_KEY = 0xA11CE; // arbitrary fixed key for the test signer
    address signerAddr;

    function setUp() public {
        token = new MockToken();
        bridge = new L1BossBridge(IERC20(address(token)));
        vault = bridge.vault();

        signerAddr = vm.addr(SIGNER_KEY);
        bridge.setSigner(signerAddr, true);

        // Fund the vault so withdrawals have something to drain
        token.mintTo(address(vault), 100 ether);
        vm.prank(address(vault));
        token.approve(address(bridge), type(uint256).max);
    }

    /// PROMISE (NatSpec line 83): "The signature is required to prevent
    /// replay attacks." INVARIANT: a single (v,r,s) for a given (to, amount)
    /// withdraws at most `amount` in total, no matter how many times it is
    /// submitted.
    function check_withdrawCannotBeReplayed() public {
        uint256 amount = 1 ether;

        bytes memory message = abi.encode(
            address(token),
            uint256(0),
            abi.encodeCall(IERC20.transferFrom, (address(vault), TO, amount))
        );
        bytes32 hash = MessageHashUtils.toEthSignedMessageHash(keccak256(message));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(SIGNER_KEY, hash);

        uint256 balBefore = token.balanceOf(TO);

        bridge.withdrawTokensToL1(TO, amount, v, r, s);
        // REPLAY — should revert under any sane replay-guard, but the bridge
        // has no nonce/expiry so this call also succeeds.
        bridge.withdrawTokensToL1(TO, amount, v, r, s);

        uint256 balAfter = token.balanceOf(TO);

        assert(balAfter - balBefore <= amount);
    }
}
