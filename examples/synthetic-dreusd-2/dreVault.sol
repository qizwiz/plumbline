// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @notice ERC4626-style yield vault for dreUSD with a two-step (queued) withdrawal.
/// @dev Shares are minted on deposit against price-per-share = totalAssets / totalSupply.
contract dreVault {
    IERC20 public immutable asset; // dreUSD
    uint256 public totalSupply;    // total shares (dreUSDs)
    mapping(address => uint256) public balanceOf;

    // queued withdrawals: shares are burned at request time; assets paid at claim time
    mapping(address => uint256) public owed; // dreUSD owed to a holder who has requested redemption
    uint256 public totalOwed;                // sum of all `owed` not yet claimed

    constructor(IERC20 _asset) { asset = _asset; }

    /// @notice dreUSD economically backing current shares.
    function totalAssets() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function _toShares(uint256 assets) internal view returns (uint256) {
        uint256 ts = totalSupply;
        return ts == 0 ? assets : (assets * ts) / totalAssets();
    }

    function _toAssets(uint256 shares) internal view returns (uint256) {
        uint256 ts = totalSupply;
        return ts == 0 ? shares : (shares * totalAssets()) / ts;
    }

    /// @notice Deposit dreUSD, mint shares at the current price-per-share.
    function deposit(uint256 assets) external returns (uint256 shares) {
        shares = _toShares(assets);
        asset.transferFrom(msg.sender, address(this), assets);
        totalSupply += shares;
        balanceOf[msg.sender] += shares;
    }

    /// @notice Step 1: burn shares now, record the dreUSD owed; paid out later by claim().
    function requestRedeem(uint256 shares) external returns (uint256 assets) {
        require(balanceOf[msg.sender] >= shares, "insufficient");
        assets = _toAssets(shares);
        balanceOf[msg.sender] -= shares;
        totalSupply -= shares;
        owed[msg.sender] += assets;
        totalOwed += assets;
    }

    /// @notice Step 2: pay out previously-requested redemption once the buffer is funded.
    function claim() external returns (uint256 assets) {
        assets = owed[msg.sender];
        require(assets > 0, "nothing owed");
        owed[msg.sender] = 0;
        totalOwed -= assets;
        asset.transfer(msg.sender, assets);
    }
}
