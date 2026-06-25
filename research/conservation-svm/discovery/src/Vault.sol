// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Vault {
    uint256 public g_totalAssets;
    mapping(address => uint256) public userShares;
    function enter(uint256 amt) external { g_totalAssets += amt; userShares[msg.sender] += amt; }
    function exit(uint256 amt) external { g_totalAssets -= amt; userShares[msg.sender] -= amt; }
}
