// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {LostAndFound} from "../LostAndFound.sol";

/// @title ReentrancyAttacker
/// @notice Test-only contract that attempts to re-enter confirmRecovery as the finder.
contract ReentrancyAttacker {
    LostAndFound public immutable TARGET;
    uint256 public listingId;
    bool public attacked;

    constructor(LostAndFound _target) {
        TARGET = _target;
    }

    function reportFound(uint256 _listingId) external {
        listingId = _listingId;
        TARGET.reportFound(_listingId);
    }

    receive() external payable {
        if (!attacked) {
            attacked = true;
            TARGET.confirmRecovery(listingId);
        }
    }
}
