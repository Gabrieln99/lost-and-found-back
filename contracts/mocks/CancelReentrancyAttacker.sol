// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {LostAndFound} from "../LostAndFound.sol";

/// @title CancelReentrancyAttacker
/// @notice Test-only contract that acts as a malicious owner and attempts to
/// re-enter cancelListing during its own refund callback.
contract CancelReentrancyAttacker {
    LostAndFound public immutable TARGET;
    uint256 public listingId;
    bool public attacked;

    constructor(LostAndFound _target) {
        TARGET = _target;
    }

    function createListing(string calldata itemCID, uint256 expirationTimestamp) external payable {
        listingId = TARGET.createListing{value: msg.value}(itemCID, expirationTimestamp);
    }

    function cancel() external {
        TARGET.cancelListing(listingId);
    }

    receive() external payable {
        if (!attacked) {
            attacked = true;
            TARGET.cancelListing(listingId);
        }
    }
}
