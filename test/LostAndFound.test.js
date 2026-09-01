const { expect } = require("chai");
const { ethers } = require("hardhat");
const {
  loadFixture,
  time,
} = require("@nomicfoundation/hardhat-network-helpers");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const Status = { Open: 0, Reported: 1, Resolved: 2, Cancelled: 3 };
const REWARD = ethers.parseEther("1");
const CID = "bafybeigdyrztestcid1234567890";

describe("LostAndFound", function () {
  async function deployFixture() {
    const [owner, finder, other] = await ethers.getSigners();
    const LostAndFound = await ethers.getContractFactory("LostAndFound");
    const contract = await LostAndFound.deploy();
    return { contract, owner, finder, other };
  }

  async function openListingFixture() {
    const base = await deployFixture();
    const tx = await base.contract
      .connect(base.owner)
      .createListing(CID, 0, { value: REWARD });
    await tx.wait();
    return { ...base, listingId: 0n };
  }

  async function reportedListingFixture() {
    const base = await openListingFixture();
    await base.contract.connect(base.finder).reportFound(base.listingId);
    return base;
  }

  describe("deployment", function () {
    it("starts with listingCount 0", async function () {
      const { contract } = await loadFixture(deployFixture);
      expect(await contract.listingCount()).to.equal(0n);
    });
  });

  describe("createListing", function () {
    it("creates a listing with correct fields and emits ListingCreated", async function () {
      const { contract, owner } = await loadFixture(deployFixture);

      await expect(contract.connect(owner).createListing(CID, 0, { value: REWARD }))
        .to.emit(contract, "ListingCreated")
        .withArgs(0n, owner.address, REWARD, CID, 0n, anyValue);

      const listing = await contract.listings(0);
      expect(listing.owner).to.equal(owner.address);
      expect(listing.finder).to.equal(ethers.ZeroAddress);
      expect(listing.reward).to.equal(REWARD);
      expect(listing.itemCID).to.equal(CID);
      expect(listing.status).to.equal(Status.Open);
      expect(listing.expirationTimestamp).to.equal(0n);
      expect(await contract.listingCount()).to.equal(1n);
    });

    it("increases contract balance by the reward", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await contract.connect(owner).createListing(CID, 0, { value: REWARD });
      expect(await ethers.provider.getBalance(await contract.getAddress())).to.equal(REWARD);
    });

    it("reverts when reward is zero", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await expect(
        contract.connect(owner).createListing(CID, 0, { value: 0 })
      ).to.be.revertedWith("Reward must be greater than zero");
    });

    it("reverts when itemCID is empty", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await expect(
        contract.connect(owner).createListing("", 0, { value: REWARD })
      ).to.be.revertedWith("CID required");
    });

    it("reverts when expirationTimestamp is in the past", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      const past = (await time.latest()) - 1;
      await expect(
        contract.connect(owner).createListing(CID, past, { value: REWARD })
      ).to.be.revertedWith("Invalid expiration");
    });

    it("assigns sequential unique IDs across multiple listings", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await contract.connect(owner).createListing(CID, 0, { value: REWARD });
      await contract.connect(owner).createListing(CID, 0, { value: REWARD });

      expect(await contract.listingCount()).to.equal(2n);
      const first = await contract.listings(0);
      const second = await contract.listings(1);
      expect(first.owner).to.equal(owner.address);
      expect(second.owner).to.equal(owner.address);
    });
  });

  describe("reportFound", function () {
    it("records the finder and flips status to Reported", async function () {
      const { contract, finder, listingId } = await loadFixture(openListingFixture);

      await expect(contract.connect(finder).reportFound(listingId))
        .to.emit(contract, "ItemReported")
        .withArgs(listingId, finder.address, anyValue);

      const listing = await contract.listings(listingId);
      expect(listing.finder).to.equal(finder.address);
      expect(listing.status).to.equal(Status.Reported);
    });

    it("reverts for a nonexistent listing", async function () {
      const { contract, finder } = await loadFixture(deployFixture);
      await expect(contract.connect(finder).reportFound(0)).to.be.revertedWith(
        "Listing does not exist"
      );
    });

    it("reverts when the listing is already Reported", async function () {
      const { contract, finder, other, listingId } = await loadFixture(reportedListingFixture);
      await expect(
        contract.connect(other).reportFound(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("reverts when the listing is Resolved", async function () {
      const { contract, owner, finder, other, listingId } = await loadFixture(reportedListingFixture);
      await contract.connect(owner).confirmRecovery(listingId);
      await expect(
        contract.connect(other).reportFound(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("reverts when the listing is Cancelled", async function () {
      const { contract, owner, other, listingId } = await loadFixture(openListingFixture);
      await contract.connect(owner).cancelListing(listingId);
      await expect(
        contract.connect(other).reportFound(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("reverts when the owner reports their own listing", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);
      await expect(
        contract.connect(owner).reportFound(listingId)
      ).to.be.revertedWith("Owner cannot report own listing");
    });

    it("reverts once the expiration has passed", async function () {
      const { contract, owner, finder } = await loadFixture(deployFixture);
      const expiration = (await time.latest()) + 3600;
      await contract.connect(owner).createListing(CID, expiration, { value: REWARD });

      await time.increaseTo(expiration + 1);

      await expect(contract.connect(finder).reportFound(0)).to.be.revertedWith(
        "Listing expired"
      );
    });

    it("does not allow a second address to overwrite the recorded finder", async function () {
      const { contract, other, listingId } = await loadFixture(reportedListingFixture);
      await expect(
        contract.connect(other).reportFound(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });
  });

  describe("rejectReport", function () {
    it("resets the listing to Open and clears the finder", async function () {
      const { contract, owner, finder, listingId } = await loadFixture(reportedListingFixture);

      await expect(contract.connect(owner).rejectReport(listingId))
        .to.emit(contract, "ReportRejected")
        .withArgs(listingId, finder.address, anyValue);

      const listing = await contract.listings(listingId);
      expect(listing.status).to.equal(Status.Open);
      expect(listing.finder).to.equal(ethers.ZeroAddress);
    });

    it("reverts for a non-owner caller", async function () {
      const { contract, other, listingId } = await loadFixture(reportedListingFixture);
      await expect(
        contract.connect(other).rejectReport(listingId)
      ).to.be.revertedWith("Not listing owner");
    });

    it("reverts for a nonexistent listing", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await expect(contract.connect(owner).rejectReport(0)).to.be.revertedWith(
        "Listing does not exist"
      );
    });

    it("reverts when the listing is not Reported", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);
      await expect(
        contract.connect(owner).rejectReport(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("allows a new address to report again after rejection", async function () {
      const { contract, owner, other, listingId } = await loadFixture(reportedListingFixture);
      await contract.connect(owner).rejectReport(listingId);

      await contract.connect(other).reportFound(listingId);
      const listing = await contract.listings(listingId);
      expect(listing.finder).to.equal(other.address);
      expect(listing.status).to.equal(Status.Reported);
    });
  });

  describe("confirmRecovery", function () {
    it("pays the finder and resolves the listing", async function () {
      const { contract, owner, finder, listingId } = await loadFixture(reportedListingFixture);

      await expect(
        contract.connect(owner).confirmRecovery(listingId)
      ).to.changeEtherBalances([contract, finder], [-REWARD, REWARD]);

      const listing = await contract.listings(listingId);
      expect(listing.status).to.equal(Status.Resolved);
      expect(listing.reward).to.equal(0n);
    });

    it("emits ListingResolved", async function () {
      const { contract, owner, finder, listingId } = await loadFixture(reportedListingFixture);
      await expect(contract.connect(owner).confirmRecovery(listingId))
        .to.emit(contract, "ListingResolved")
        .withArgs(listingId, finder.address, REWARD, anyValue);
    });

    it("reverts for a non-owner caller", async function () {
      const { contract, other, listingId } = await loadFixture(reportedListingFixture);
      await expect(
        contract.connect(other).confirmRecovery(listingId)
      ).to.be.revertedWith("Not listing owner");
    });

    it("reverts for a nonexistent listing", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await expect(contract.connect(owner).confirmRecovery(0)).to.be.revertedWith(
        "Listing does not exist"
      );
    });

    it("reverts when the listing is still Open", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);
      await expect(
        contract.connect(owner).confirmRecovery(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("reverts on a second call for the same listing", async function () {
      const { contract, owner, listingId } = await loadFixture(reportedListingFixture);
      await contract.connect(owner).confirmRecovery(listingId);
      await expect(
        contract.connect(owner).confirmRecovery(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("blocks a reentrant call via the ReentrancyGuard", async function () {
      const { contract, owner } = await loadFixture(openListingFixture);
      const Attacker = await ethers.getContractFactory("ReentrancyAttacker");
      const attacker = await Attacker.deploy(await contract.getAddress());

      await attacker.reportFound(0);

      // The attacker's receive() tries to re-enter confirmRecovery. The
      // ReentrancyGuard reverts that inner call, which unwinds the ETH
      // transfer too, so the whole outer confirmRecovery reverts with no
      // funds moved and no double payout — proving the guard is effective.
      await expect(
        contract.connect(owner).confirmRecovery(0)
      ).to.be.revertedWith("Transfer failed");

      expect(await ethers.provider.getBalance(await contract.getAddress())).to.equal(REWARD);
      const listing = await contract.listings(0);
      expect(listing.status).to.equal(Status.Reported);
      expect(listing.reward).to.equal(REWARD);
    });
  });

  describe("cancelListing", function () {
    it("refunds the owner and cancels the listing", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);

      await expect(
        contract.connect(owner).cancelListing(listingId)
      ).to.changeEtherBalances([contract, owner], [-REWARD, REWARD]);

      const listing = await contract.listings(listingId);
      expect(listing.status).to.equal(Status.Cancelled);
      expect(listing.reward).to.equal(0n);
    });

    it("emits ListingCancelled", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);
      await expect(contract.connect(owner).cancelListing(listingId))
        .to.emit(contract, "ListingCancelled")
        .withArgs(listingId, owner.address, REWARD, anyValue);
    });

    it("reverts for a non-owner caller", async function () {
      const { contract, other, listingId } = await loadFixture(openListingFixture);
      await expect(
        contract.connect(other).cancelListing(listingId)
      ).to.be.revertedWith("Not listing owner");
    });

    it("reverts for a nonexistent listing", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      await expect(contract.connect(owner).cancelListing(0)).to.be.revertedWith(
        "Listing does not exist"
      );
    });

    it("reverts when the listing is already Reported", async function () {
      const { contract, owner, listingId } = await loadFixture(reportedListingFixture);
      await expect(
        contract.connect(owner).cancelListing(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("reverts when the listing is already Cancelled", async function () {
      const { contract, owner, listingId } = await loadFixture(openListingFixture);
      await contract.connect(owner).cancelListing(listingId);
      await expect(
        contract.connect(owner).cancelListing(listingId)
      ).to.be.revertedWith("Invalid listing status");
    });

    it("succeeds even after the expiration has passed", async function () {
      const { contract, owner } = await loadFixture(deployFixture);
      const expiration = (await time.latest()) + 3600;
      await contract.connect(owner).createListing(CID, expiration, { value: REWARD });
      await time.increaseTo(expiration + 1);

      await expect(
        contract.connect(owner).cancelListing(0)
      ).to.changeEtherBalances([contract, owner], [-REWARD, REWARD]);
    });
  });

  describe("integration", function () {
    it("full happy path: create -> report -> confirm", async function () {
      const { contract, owner, finder } = await loadFixture(deployFixture);
      await contract.connect(owner).createListing(CID, 0, { value: REWARD });
      await contract.connect(finder).reportFound(0);

      await expect(
        contract.connect(owner).confirmRecovery(0)
      ).to.changeEtherBalances([owner, finder], [0n, REWARD]);

      const listing = await contract.listings(0);
      expect(listing.status).to.equal(Status.Resolved);
    });

    it("reject-then-resolve: finder A is rejected, finder B gets paid", async function () {
      const { contract, owner, finder, other } = await loadFixture(deployFixture);
      await contract.connect(owner).createListing(CID, 0, { value: REWARD });

      await contract.connect(finder).reportFound(0);
      await contract.connect(owner).rejectReport(0);
      await contract.connect(other).reportFound(0);

      await expect(
        contract.connect(owner).confirmRecovery(0)
      ).to.changeEtherBalances([finder, other], [0n, REWARD]);

      const listing = await contract.listings(0);
      expect(listing.status).to.equal(Status.Resolved);
      expect(listing.finder).to.equal(other.address);
    });
  });
});
