const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const STATUS_NAMES = ["Open", "Reported", "Resolved", "Cancelled"];

function loadDeployedAddress() {
  const deploymentPath = path.join(__dirname, "..", "deployments", "sepolia.json");
  const deployment = JSON.parse(fs.readFileSync(deploymentPath, "utf8"));
  return deployment.address;
}

async function main() {
  const txHash = process.env.TX_HASH;
  if (!txHash) {
    throw new Error(
      "Set TX_HASH to the createListing transaction hash, e.g.\n" +
        "  TX_HASH=0x... npx hardhat run scripts/check-listing.js --network sepolia",
    );
  }

  const contractAddress = process.env.CONTRACT_ADDRESS || loadDeployedAddress();
  const contract = await hre.ethers.getContractAt(
    "LostAndFound",
    contractAddress,
    hre.ethers.provider,
  );

  const receipt = await hre.ethers.provider.getTransactionReceipt(txHash);
  if (!receipt) {
    throw new Error(`No receipt found for ${txHash} on this network`);
  }

  let listingId;
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed?.name === "ListingCreated") {
        listingId = parsed.args.listingId;
        break;
      }
    } catch {
      // Not a log this contract's interface can parse; skip it.
    }
  }

  if (listingId === undefined) {
    throw new Error("No ListingCreated event found in that transaction's logs");
  }

  const listing = await contract.listings(listingId);

  console.log("Contract:        ", contractAddress);
  console.log("Listing ID:      ", listingId.toString());
  console.log("Status:          ", STATUS_NAMES[Number(listing.status)]);
  console.log("Owner:           ", listing.owner);
  console.log("Item CID:        ", listing.itemCID);
  console.log("Reward:          ", hre.ethers.formatEther(listing.reward), "ETH");
  console.log(
    "Created at:      ",
    new Date(Number(listing.createdAt) * 1000).toISOString(),
  );
  console.log(
    "Expiration:      ",
    listing.expirationTimestamp === 0n
      ? "none"
      : new Date(Number(listing.expirationTimestamp) * 1000).toISOString(),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
