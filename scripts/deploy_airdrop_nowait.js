import hre from "hardhat";

async function main() {
  console.log("=" .repeat(60));
  console.log("  Deploying AirdropDistributor (No Wait)");
  console.log("=" .repeat(60));
  console.log();

  const network = hre.network.name;
  const [deployer] = await hre.ethers.getSigners();
  const balance = await hre.ethers.provider.getBalance(deployer.address);

  console.log("Network:", network);
  console.log("Deployer:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "KAS");
  console.log();

  if (balance === 0n) {
    throw new Error("Deployer has 0 balance!");
  }

  console.log("Loading contract factory...");
  const AirdropDistributor = await hre.ethers.getContractFactory("AirdropDistributor");

  console.log("Sending deployment transaction...");
  const distributor = await AirdropDistributor.deploy();
  
  const txHash = distributor.deploymentTransaction()?.hash;
  console.log();
  console.log("✅ TRANSACTION SENT!");
  console.log("=" .repeat(60));
  console.log("TX Hash:", txHash);
  console.log("Explorer:", `https://explorer.testnet.kasplextest.xyz/tx/${txHash}`);
  console.log();
  console.log("Attempting to get contract address (may fail if not yet mined)...");
  
  try {
    // Try with a short timeout
    const receipt = await hre.ethers.provider.waitForTransaction(txHash, 1, 15000); // 15 second timeout
    if (receipt && receipt.contractAddress) {
      console.log();
      console.log("✅ MINED!");
      console.log("Contract:", receipt.contractAddress);
      console.log("Block:", receipt.blockNumber);
      console.log("Gas Used:", receipt.gasUsed.toString());
    }
  } catch (timeoutError) {
    console.log();
    console.log("⏰ Transaction still pending after 15s");
    console.log("Check the explorer link above for status");
    console.log("Once confirmed, the contract address will be shown");
  }
  
  console.log();
}

main()
  .then(() => {
    console.log("Script completed (tx sent, may still be pending)");
    process.exit(0);
  })
  .catch((error) => {
    console.error("\n❌ Error:");
    console.error(error);
    process.exit(1);
  });
