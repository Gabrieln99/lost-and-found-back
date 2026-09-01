const hre = require("hardhat");

async function main() {
  const LostAndFound = await hre.ethers.getContractFactory("LostAndFound");
  const lostAndFound = await LostAndFound.deploy();
  await lostAndFound.waitForDeployment();

  console.log("LostAndFound deployed to:", await lostAndFound.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
