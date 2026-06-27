// SPDX-License-Identifier: MIT
// NEGATIVE CONTROL #2 — exposes a parser false-positive in conserve.py's proposer.
//
// Identical in spirit to AdminVault (access-control admin contract, conservation is the
// WRONG law), but it ALSO has an admin `_burn`. No single function forms a deposit/withdraw
// inverse pair, so the correct behavior is still DECLINE.
//
// With the original `functions()` regex, the IERC20 interface method declarations are
// mis-parsed as a function whose brace-matched "body" is the ENTIRE contract interior.
// That phantom body contains transferFrom-in + _mint (a phantom deposit) AND _burn +
// .transfer-out (a phantom withdraw) -> the proposer FALSE-PROPOSES a conservation invariant.
// That is a precision-1.0-by-soundness violation at the proposer stage. This fixture is the
// regression guard: it must DECLINE once the parser is fixed to ignore `;`-terminated decls.
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
}

contract AdminVaultBurn {
    address public owner;
    IERC20 public rewardToken;

    constructor(address _t) { owner = msg.sender; rewardToken = IERC20(_t); }

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }

    function adminMint(address to, uint256 amt) external onlyOwner { _mint(to, amt); }
    function adminBurn(address from, uint256 amt) external onlyOwner { _burn(from, amt); }
    function sweep(address to, uint256 amt) external onlyOwner { rewardToken.transfer(to, amt); }
    function fund(uint256 amt) external { rewardToken.transferFrom(msg.sender, address(this), amt); }
    function transferOwnership(address n) external onlyOwner { owner = n; }

    function _mint(address, uint256) internal {}
    function _burn(address, uint256) internal {}
}
