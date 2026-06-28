// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;

import {StakingRewards} from "../src/StakingRewards.sol";
import {StakingRewardsMutant} from "../src/StakingRewardsMutant.sol";

interface Vm { function assume(bool) external; }
Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

// Minimal ERC20 so stake()/withdraw() safeTransfer paths SUCCEED — without this the
// real contract's stakingToken.safeTransferFrom/safeTransfer revert before the assert,
// making any halmos PASS vacuous. This token is harness plumbing only; the induced
// conservation invariant (and its assertions) are unchanged from discover.py's emission.
contract MockERC20 {
    mapping(address => uint256) public balanceOf;
    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function transfer(address to, uint256 a) external returns (bool){ balanceOf[msg.sender]-=a; balanceOf[to]+=a; return true; }
    function transferFrom(address f,address t,uint256 a) external returns (bool){ balanceOf[f]-=a; balanceOf[t]+=a; return true; }
    function approve(address,uint256) external returns (bool){ return true; }
    function allowance(address,address) external pure returns (uint256){ return type(uint256).max; }
}

contract DiscoveredTest {
    StakingRewards staking;
    MockERC20 stk;

    function setUp() public {
        stk = new MockERC20();
        staking = new StakingRewards();
        staking.initialize(address(this), address(stk), address(stk), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        // bound symbolic amounts to avoid overflow / underflow noise
        vm.assume(a > 0 && a < 1e30);
        vm.assume(b > 0 && b <= a); // can only withdraw what was staked

        address user = address(this);
        stk.mint(user, a); // fund the staker so safeTransferFrom succeeds

        // --- exercise stake: aggregate and holding must move together ---
        uint256 aggBeforeStake = staking.totalSupply();
        uint256 holdBeforeStake = staking.balanceOf(user);
        staking.stake(a);
        uint256 aggAfterStake = staking.totalSupply();
        uint256 holdAfterStake = staking.balanceOf(user);

        int256 aggDeltaStake = int256(aggAfterStake) - int256(aggBeforeStake);
        int256 holdDeltaStake = int256(holdAfterStake) - int256(holdBeforeStake);
        assert(aggDeltaStake == holdDeltaStake);

        // --- exercise withdraw: aggregate and holding must move together ---
        uint256 aggBeforeWd = staking.totalSupply();
        uint256 holdBeforeWd = staking.balanceOf(user);
        staking.withdraw(b);
        uint256 aggAfterWd = staking.totalSupply();
        uint256 holdAfterWd = staking.balanceOf(user);

        int256 aggDeltaWd = int256(aggAfterWd) - int256(aggBeforeWd);
        int256 holdDeltaWd = int256(holdAfterWd) - int256(holdBeforeWd);
        assert(aggDeltaWd == holdDeltaWd);
    }
}

// SAME emitted invariant + harness, retargeted at the 1-line mutant (withdraw() missing
// `_totalSupply -= amount`). Discrimination control: the induced law must CATCH this.
contract DiscoveredTestMutant {
    StakingRewardsMutant staking;
    MockERC20 stk;

    function setUp() public {
        stk = new MockERC20();
        staking = new StakingRewardsMutant();
        staking.initialize(address(this), address(stk), address(stk), address(this), false);
    }

    function check_invariant(uint256 a, uint256 b) public {
        vm.assume(a > 0 && a < 1e30);
        vm.assume(b > 0 && b <= a);

        address user = address(this);
        stk.mint(user, a);

        uint256 aggBeforeStake = staking.totalSupply();
        uint256 holdBeforeStake = staking.balanceOf(user);
        staking.stake(a);
        uint256 aggAfterStake = staking.totalSupply();
        uint256 holdAfterStake = staking.balanceOf(user);

        int256 aggDeltaStake = int256(aggAfterStake) - int256(aggBeforeStake);
        int256 holdDeltaStake = int256(holdAfterStake) - int256(holdBeforeStake);
        assert(aggDeltaStake == holdDeltaStake);

        uint256 aggBeforeWd = staking.totalSupply();
        uint256 holdBeforeWd = staking.balanceOf(user);
        staking.withdraw(b);
        uint256 aggAfterWd = staking.totalSupply();
        uint256 holdAfterWd = staking.balanceOf(user);

        int256 aggDeltaWd = int256(aggAfterWd) - int256(aggBeforeWd);
        int256 holdDeltaWd = int256(holdAfterWd) - int256(holdBeforeWd);
        assert(aggDeltaWd == holdDeltaWd);
    }
}
