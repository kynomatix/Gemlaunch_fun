import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Deploy AirdropDistributor Helper Contract
 * 
 * This is a simple stateless helper contract with no constructor parameters.
 * It provides batch transfer functionality for token airdrops.
 * 
 * Usage:
 * npx hardhat run scripts/deploy_airdrop_distributor.js --network kasplex_testnet
 */
async function main() {
  console.log("═══════════════════════════════════════════════════════════");
  console.log("   Deploying AirdropDistributor Helper Contract");
  console.log("═══════════════════════════════════════════════════════════\n");

  const network = hre.network.name;
  console.log(`Network: ${network}`);
  
  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log(`Deployer: ${deployer.address}`);
  
  // Check deployer balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`Balance: ${hre.ethers.formatEther(balance)} KAS\n`);
  
  if (balance === 0n) {
    throw new Error("⚠️  Deployer has 0 balance. Fund the wallet first!");
  }

  console.log("──────────────────────────────────────────────────────────");
  console.log("1. Deploying AirdropDistributor...");
  console.log("──────────────────────────────────────────────────────────\n");

  // Deploy AirdropDistributor (no constructor parameters)
  const AirdropDistributor = await hre.ethers.getContractFactory("AirdropDistributor");
  const distributor = await AirdropDistributor.deploy();
  await distributor.waitForDeployment();

  const distributorAddress = await distributor.getAddress();
  console.log(`✅ AirdropDistributor deployed: ${distributorAddress}\n`);

  console.log("──────────────────────────────────────────────────────────");
  console.log("2. Verifying Deployment");
  console.log("──────────────────────────────────────────────────────────\n");

  // Verify the contract has code
  const code = await hre.ethers.provider.getCode(distributorAddress);
  if (code === "0x") {
    throw new Error("⚠️  Contract deployment failed - no code at address");
  }
  
  console.log(`✅ Contract code verified (${code.length} bytes)\n`);

  console.log("──────────────────────────────────────────────────────────");
  console.log("3. Saving Deployment Info");
  console.log("──────────────────────────────────────────────────────────\n");

  // Save deployment info
  const deploymentInfo = {
    network: network,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contract: {
      name: "AirdropDistributor",
      address: distributorAddress,
      blockNumber: (await distributor.deploymentTransaction()).blockNumber
    }
  };

  // Save to deployments directory
  const deploymentsDir = path.join(process.cwd(), "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const filename = `airdrop_distributor_${network}_${Date.now()}.json`;
  const filepath = path.join(deploymentsDir, filename);
  fs.writeFileSync(filepath, JSON.stringify(deploymentInfo, null, 2));

  console.log(`✅ Deployment info saved: ${filepath}\n`);

  console.log("═══════════════════════════════════════════════════════════");
  console.log("   Deployment Complete");
  console.log("═══════════════════════════════════════════════════════════\n");

  console.log("📋 Summary:");
  console.log(`   AirdropDistributor: ${distributorAddress}`);
  console.log(`   Network:            ${network}`);
  console.log(`   Chain ID:           ${deploymentInfo.chainId}`);
  console.log("");
  console.log("⚠️  IMPORTANT: Update services/web3_service.py with:");
  console.log(`   AIRDROP_DISTRIBUTOR_ADDRESS = "${distributorAddress}"`);
  console.log("");
  console.log("Next Steps:");
  console.log("1. Update web3_service.py with the contract address");
  console.log("2. Add contract ABI loading logic");
  console.log("3. Test batch transfer functionality");
  console.log("");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
