// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
import {StakingRewards} from "../src/StakingRewards.sol";
import {StakingRewardsMutant} from "../src/StakingRewardsMutant.sol";

interface Vm { function assume(bool) external; }

contract MockERC20 {
    mapping(address => uint256) public balanceOf;
    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function transfer(address to, uint256 a) external returns (bool){ balanceOf[msg.sender]-=a; balanceOf[to]+=a; return true; }
    function transferFrom(address f,address t,uint256 a) external returns (bool){ balanceOf[f]-=a; balanceOf[t]+=a; return true; }
    function approve(address,uint256) external returns (bool){ return true; }
    function allowance(address,address) external pure returns (uint256){ return type(uint256).max; }
}

contract IdleConservation {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);
    StakingRewards s; MockERC20 stk;
    function setUp() public { stk = new MockERC20(); s = new StakingRewards(); s.initialize(address(this), address(stk), address(stk), address(this), true); }
    function check_idleConservation(uint256 stakeAmt, uint256 wAmt) public {
        vm.assume(stakeAmt > 0 && stakeAmt < type(uint96).max); vm.assume(wAmt > 0 && wAmt <= stakeAmt);
        stk.mint(address(this), stakeAmt); s.stake(stakeAmt);
        int256 A0=int256(s.totalSupply()); int256 m0=int256(s.balanceOf(address(this)));
        s.withdraw(wAmt);
        int256 A1=int256(s.totalSupply()); int256 m1=int256(s.balanceOf(address(this)));
        assert(A1 - A0 == m1 - m0);
    }
}

contract IdleConservationMutant {
    Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);
    StakingRewardsMutant s; MockERC20 stk;
    function setUp() public { stk = new MockERC20(); s = new StakingRewardsMutant(); s.initialize(address(this), address(stk), address(stk), address(this), true); }
    function check_idleConservation(uint256 stakeAmt, uint256 wAmt) public {
        vm.assume(stakeAmt > 0 && stakeAmt < type(uint96).max); vm.assume(wAmt > 0 && wAmt <= stakeAmt);
        stk.mint(address(this), stakeAmt); s.stake(stakeAmt);
        int256 A0=int256(s.totalSupply()); int256 m0=int256(s.balanceOf(address(this)));
        s.withdraw(wAmt);
        int256 A1=int256(s.totalSupply()); int256 m1=int256(s.balanceOf(address(this)));
        assert(A1 - A0 == m1 - m0);
    }
}
