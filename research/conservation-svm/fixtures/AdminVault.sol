// SPDX-License-Identifier: MIT
// NEGATIVE CONTROL for conserve.py's structural proposer.
//
// This is an access-control / admin contract. Conservation is the WRONG law for it.
// It DELIBERATELY contains all three tempting trigger keywords — `_mint`, `.transfer`,
// `.transferFrom(..., address(this), ...)` — but NEVER as a deposit/withdraw inverse pair
// within a single function:
//   * adminMint  : `_mint` WITHOUT a matching transferFrom-into-this  -> not a deposit
//   * sweep      : `.transfer` OUT WITHOUT a matching `_burn`          -> not a withdraw
//   * fund       : transferFrom-into-this WITHOUT a `_mint`           -> not a deposit
//
// A proposer that fired on keyword PRESENCE alone would emit a meaningless conservation
// property here, and halmos would then either pass it vacuously (false confidence) or
// fail it spuriously (a false positive that breaks the precision-1.0-by-soundness claim).
// The correct behavior is to DECLINE: no inverse-op pair, no conservation invariant.
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
}

contract AdminVault {
    address public owner;
    mapping(address => bool) public operators;
    IERC20 public rewardToken;

    constructor(address _t) { owner = msg.sender; rewardToken = IERC20(_t); }

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }

    // admin mint: `_mint` present, but no transferFrom-into-this in this body -> NOT a deposit
    function adminMint(address to, uint256 amt) external onlyOwner { _mint(to, amt); }

    // admin sweep: `.transfer` out present, but no `_burn` in this body -> NOT a withdraw
    function sweep(address to, uint256 amt) external onlyOwner { rewardToken.transfer(to, amt); }

    // pull funding: transferFrom-into-this present, but no `_mint` in this body -> NOT a deposit
    function fund(uint256 amt) external { rewardToken.transferFrom(msg.sender, address(this), amt); }

    function setOperator(address op, bool ok) external onlyOwner { operators[op] = ok; }
    function transferOwnership(address n) external onlyOwner { owner = n; }

    function _mint(address, uint256) internal {}
}
