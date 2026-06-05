// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @notice Stake dreUSD, earn linearly-streamed rewards (Synthetix-style accumulator).
/// @dev Operated by a single trusted REWARDS_ADMIN.
contract dreStaking {
    IERC20 public immutable token; // dreUSD (stake + reward are the same asset here)
    address public immutable REWARDS_ADMIN;

    uint256 public constant DURATION = 7 days;

    uint256 public totalStaked;
    mapping(address => uint256) public staked;

    uint256 public rewardRate;            // dreUSD per second
    uint256 public periodFinish;
    uint256 public lastUpdate;
    uint256 public rewardPerTokenStored;  // scaled by 1e18
    mapping(address => uint256) public userPaid;     // rewardPerToken already accounted, per user
    mapping(address => uint256) public rewards;      // accrued, claimable

    uint256 public reserve;               // dreUSD held for rewards

    constructor(IERC20 _token, address _admin) {
        token = _token;
        REWARDS_ADMIN = _admin;
    }

    modifier onlyAdmin() {
        require(msg.sender == REWARDS_ADMIN, "not admin");
        _;
    }

    function _lastApplicable() internal view returns (uint256) {
        return block.timestamp < periodFinish ? block.timestamp : periodFinish;
    }

    function rewardPerToken() public view returns (uint256) {
        if (totalStaked == 0) return rewardPerTokenStored;
        uint256 elapsed = _lastApplicable() - lastUpdate;
        return rewardPerTokenStored + (elapsed * rewardRate * 1e18) / totalStaked;
    }

    /// @notice Rewards accrued to `who` but not yet claimed.
    function earned(address who) public view returns (uint256) {
        uint256 delta = rewardPerToken() - userPaid[who];
        // round to 1e18 scale
        return rewards[who] + (staked[who] * delta + (1e18 - 1)) / 1e18;
    }

    function _update(address who) internal {
        rewardPerTokenStored = rewardPerToken();
        lastUpdate = _lastApplicable();
        if (who != address(0)) {
            rewards[who] = earned(who);
            userPaid[who] = rewardPerTokenStored;
        }
    }

    function stake(uint256 amount) external {
        _update(msg.sender);
        token.transferFrom(msg.sender, address(this), amount);
        totalStaked += amount;
        staked[msg.sender] += amount;
    }

    function unstake(uint256 amount) external {
        _update(msg.sender);
        require(staked[msg.sender] >= amount, "insufficient");
        totalStaked -= amount;
        staked[msg.sender] -= amount;
        token.transfer(msg.sender, amount);
    }

    function claim() external {
        _update(msg.sender);
        uint256 r = rewards[msg.sender];
        if (r > 0) {
            rewards[msg.sender] = 0;
            reserve -= r;
            token.transfer(msg.sender, r);
        }
    }

    /// @notice Set the per-second reward rate.
    function setRewardRate(uint256 newRate) external {
        _update(address(0));
        rewardRate = newRate;
    }

    /// @notice Fund a fresh reward period with `amount` dreUSD.
    function fundRewards(uint256 amount) external onlyAdmin {
        _update(address(0));
        token.transferFrom(msg.sender, address(this), amount);
        reserve += amount;
        rewardRate = amount / DURATION;
        lastUpdate = block.timestamp;
        periodFinish = block.timestamp + DURATION;
    }
}
