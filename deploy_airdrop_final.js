import hre from "hardhat";
import fs from "fs";
import path from "path";

async function main() {
  console.log("Deploying AirdropDistributor (no gas estimation)...\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "KAS\n");

  console.log("Loading contract...");
  const AirdropDistributor = await hre.ethers.getContractFactory("AirdropDistributor");
  
  console.log("Deploying with hardcoded gas limit (no estimation)...");
  const contract = await AirdropDistributor.deploy({
    gasLimit: 1000000  // Hardcode 1M gas - no estimation
  });
  
  const txHash = contract.deploymentTransaction()?.hash;
  console.log("\n✅ TX SENT:", txHash);
  console.log("Explorer: https://explorer.testnet.kasplextest.xyz/tx/" + txHash);
  console.log("\nWaiting for confirmation...");
  
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  
  console.log("\n✅ DEPLOYED!");
  console.log("Contract:", address);
  console.log("Explorer: https://explorer.testnet.kasplextest.xyz/address/" + address);
  
  // Save deployment info
  const deploymentInfo = {
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    contract: {
      name: "AirdropDistributor",
      address: address,
      transactionHash: txHash,
      blockNumber: (await hre.ethers.provider.getBlock('latest')).number
    },
    deployer: deployer.address,
    timestamp: new Date().toISOString()
  };
  
  const deploymentsDir = path.join(process.cwd(), "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }
  
  const filename = `airdrop_distributor_kasplex_testnet.json`;
  const filepath = path.join(deploymentsDir, filename);
  fs.writeFileSync(filepath, JSON.stringify(deploymentInfo, null, 2));
  
  console.log("\nDeployment info saved:", filepath);
  console.log("\nUpdate services/web3_service.py with:");
  console.log(`AIRDROP_DISTRIBUTOR_ADDRESS = "${address}"`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Error:", error.message);
    process.exit(1);
  });
