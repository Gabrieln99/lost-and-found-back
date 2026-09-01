// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title LostAndFound
/// @notice Escrows a reward for a lost item until the owner confirms recovery.
contract LostAndFound is ReentrancyGuard {
    enum Status {
        Open,
        Reported,
        Resolved,
        Cancelled
    }

    struct Listing {
        address owner;
        address finder;
        uint256 reward;
        string itemCID;
        Status status;
        uint256 createdAt;
        uint256 expirationTimestamp;
    }

    mapping(uint256 => Listing) public listings;
    uint256 public listingCount;

    event ListingCreated(
        uint256 indexed listingId,
        address indexed owner,
        uint256 reward,
        string itemCID,
        uint256 expirationTimestamp,
        uint256 createdAt
    );
    event ItemReported(uint256 indexed listingId, address indexed finder, uint256 timestamp);
    event ReportRejected(uint256 indexed listingId, address indexed rejectedFinder, uint256 timestamp);
    event ListingResolved(uint256 indexed listingId, address indexed finder, uint256 reward, uint256 timestamp);
    event ListingCancelled(uint256 indexed listingId, address indexed owner, uint256 refundedAmount, uint256 timestamp);

    modifier listingExists(uint256 listingId) {
        require(listingId < listingCount, "Listing does not exist");
        _;
    }

    modifier onlyListingOwner(uint256 listingId) {
        require(listings[listingId].owner == msg.sender, "Not listing owner");
        _;
    }

    modifier inStatus(uint256 listingId, Status expected) {
        require(listings[listingId].status == expected, "Invalid listing status");
        _;
    }

    /// @notice Publish a lost-item listing and lock the reward in escrow.
    function createListing(string calldata itemCID, uint256 expirationTimestamp)
        external
        payable
        returns (uint256 listingId)
    {
        require(msg.value > 0, "Reward must be greater than zero");
        require(bytes(itemCID).length > 0, "CID required");
        require(
            expirationTimestamp == 0 || expirationTimestamp > block.timestamp,
            "Invalid expiration"
        );

        listingId = listingCount++;
        listings[listingId] = Listing({
            owner: msg.sender,
            finder: address(0),
            reward: msg.value,
            itemCID: itemCID,
            status: Status.Open,
            createdAt: block.timestamp,
            expirationTimestamp: expirationTimestamp
        });

        emit ListingCreated(listingId, msg.sender, msg.value, itemCID, expirationTimestamp, block.timestamp);
    }

    /// @notice Report that the item has been found. Open to any address; first caller wins.
    function reportFound(uint256 listingId)
        external
        listingExists(listingId)
        inStatus(listingId, Status.Open)
    {
        Listing storage listing = listings[listingId];
        require(msg.sender != listing.owner, "Owner cannot report own listing");
        require(
            listing.expirationTimestamp == 0 || block.timestamp <= listing.expirationTimestamp,
            "Listing expired"
        );

        listing.finder = msg.sender;
        listing.status = Status.Reported;

        emit ItemReported(listingId, msg.sender, block.timestamp);
    }

    /// @notice Owner rejects a false/malicious found report, returning the listing to Open.
    function rejectReport(uint256 listingId)
        external
        listingExists(listingId)
        onlyListingOwner(listingId)
        inStatus(listingId, Status.Reported)
    {
        Listing storage listing = listings[listingId];
        address rejectedFinder = listing.finder;
        listing.finder = address(0);
        listing.status = Status.Open;

        emit ReportRejected(listingId, rejectedFinder, block.timestamp);
    }

    /// @notice Owner confirms recovery; releases the escrowed reward to the finder.
    function confirmRecovery(uint256 listingId)
        external
        nonReentrant
        listingExists(listingId)
        onlyListingOwner(listingId)
        inStatus(listingId, Status.Reported)
    {
        Listing storage listing = listings[listingId];
        address recipient = listing.finder;
        uint256 payoutAmount = listing.reward;

        listing.status = Status.Resolved;
        listing.reward = 0;

        emit ListingResolved(listingId, recipient, payoutAmount, block.timestamp);

        (bool ok, ) = recipient.call{value: payoutAmount}("");
        require(ok, "Transfer failed");
    }

    /// @notice Owner cancels an unclaimed listing and reclaims the escrowed reward.
    function cancelListing(uint256 listingId)
        external
        nonReentrant
        listingExists(listingId)
        onlyListingOwner(listingId)
        inStatus(listingId, Status.Open)
    {
        Listing storage listing = listings[listingId];
        uint256 refundAmount = listing.reward;

        listing.status = Status.Cancelled;
        listing.reward = 0;

        emit ListingCancelled(listingId, msg.sender, refundAmount, block.timestamp);

        (bool ok, ) = msg.sender.call{value: refundAmount}("");
        require(ok, "Refund failed");
    }
}
