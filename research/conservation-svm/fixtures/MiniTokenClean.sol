// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract MiniTokenClean {
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    function mint(address to, uint256 amt) external { totalSupply += amt; balanceOf[to] += amt; }
    function burn(uint256 amt) external { totalSupply -= amt; balanceOf[msg.sender] -= amt; }
}
