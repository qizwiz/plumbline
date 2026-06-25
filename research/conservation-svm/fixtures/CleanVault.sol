// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ERC20} from "solmate/tokens/ERC20.sol";
interface IUSDC { function transferFrom(address,address,uint256) external returns (bool);
                  function transfer(address,uint256) external returns (bool); }
contract CleanVault is ERC20 {
    IUSDC public immutable usdc;
    constructor(address _usdc) ERC20("v","v",18) { usdc = IUSDC(_usdc); }
    function mint(uint256 amt) external { usdc.transferFrom(msg.sender, address(this), amt); _mint(msg.sender, amt); }
    function redeem(uint256 amt) external { _burn(msg.sender, amt); usdc.transfer(msg.sender, amt); }
}
