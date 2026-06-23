// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// Minimal faithful extract of morph L1Staking's staker-set / bitmap logic.
/// getStakersFromBitmap is copied VERBATIM from L1Staking.sol (lines 406-426 of the
/// audited commit 22ca805) — the bug must be preserved exactly, not abstracted.
/// slash() uses getStakersFromBitmap to decide who to punish, so any staker the
/// bitmap fails to recover is immune to slashing.
contract StakerBitmap {
    address[255] public stakerSet;

    /// populate every slot with a distinct nonzero address: slot i -> address(i+1)
    function fill() external {
        for (uint256 i = 0; i < 255; i++) {
            stakerSet[i] = address(uint160(i + 1));
        }
    }

    /// VERBATIM from L1Staking.sol — note `i < 255`.
    function getStakersFromBitmap(uint256 bitmap) public view returns (address[] memory stakerAddrs) {
        // skip first bit
        uint256 _bitmap = bitmap >> 1;
        uint256 stakersLength = 0;
        while (_bitmap > 0) {
            stakersLength = stakersLength + 1;
            _bitmap = _bitmap & (_bitmap - 1);
        }

        stakerAddrs = new address[](stakersLength);
        uint256 index = 0;
        for (uint8 i = 1; i < 255; i++) {
            if ((bitmap & (1 << i)) > 0) {
                stakerAddrs[index] = stakerSet[i - 1];
                index = index + 1;
                if (index >= stakersLength) {
                    break;
                }
            }
        }
    }
}
