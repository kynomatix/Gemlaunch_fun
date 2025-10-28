import hre from "hardhat";
import fs from "fs";
import path from "path";

async function main() {
  console.log("🚀 Starting QuoterV2 deployment to Kasplex Testnet...\n");

  // Network configuration
  const network = hre.network.name;
  console.log(`📡 Network: ${network}`);
  console.log(`⛓️  Chain ID: ${hre.network.config.chainId}\n`);

  // Contract constructor parameters
  const FACTORY_ADDRESS = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8";
  const WKAS_ADDRESS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94";

  console.log("📝 Deployment Parameters:");
  console.log(`   Factory: ${FACTORY_ADDRESS}`);
  console.log(`   WKAS: ${WKAS_ADDRESS}\n`);

  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log(`👤 Deployer: ${deployer.address}`);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`💰 Balance: ${hre.ethers.formatEther(balance)} TKAS\n`);

  // Deploy QuoterV2
  console.log("📦 Deploying QuoterV2 contract...");
  const QuoterV2 = await hre.ethers.getContractFactory(
    "contracts/kaspa-v3/periphery/lens/QuoterV2.sol:QuoterV2"
  );
  
  const quoterV2 = await QuoterV2.deploy(FACTORY_ADDRESS, WKAS_ADDRESS);
  await quoterV2.waitForDeployment();

  const quoterV2Address = await quoterV2.getAddress();
  console.log(`✅ QuoterV2 deployed to: ${quoterV2Address}\n`);

  // Verify deployment by checking bytecode
  console.log("🔍 Verifying deployment...");
  const code = await hre.ethers.provider.getCode(quoterV2Address);
  
  if (code === "0x") {
    throw new Error("❌ No bytecode at deployed address!");
  }
  
  console.log(`✅ Bytecode verified (${code.length} bytes)\n`);

  // Verify constructor parameters
  console.log("🔍 Verifying contract state...");
  const factory = await quoterV2.factory();
  const weth9 = await quoterV2.WETH9();
  
  console.log(`   Factory: ${factory} ${factory === FACTORY_ADDRESS ? '✓' : '✗'}`);
  console.log(`   WETH9: ${weth9} ${weth9 === WKAS_ADDRESS ? '✓' : '✗'}\n`);

  // Save deployment information
  console.log("💾 Saving deployment info...");
  const deployedAddressesPath = path.join(process.cwd(), "contracts", "deployed_addresses.json");
  
  let deployedData = {};
  if (fs.existsSync(deployedAddressesPath)) {
    deployedData = JSON.parse(fs.readFileSync(deployedAddressesPath, "utf8"));
  }

  // Update with new QuoterV2 address
  deployedData.contracts = deployedData.contracts || {};
  deployedData.contracts.QuoterV2 = {
    version: "V1",
    address: quoterV2Address,
    deployedAt: new Date().toISOString().split('T')[0],
    factory: FACTORY_ADDRESS,
    wkas: WKAS_ADDRESS,
    notes: "Kaspa Finance V3 QuoterV2 - deployed from V3-Periphery-Contracts repo"
  };
  
  deployedData.lastUpdated = new Date().toISOString().split('T')[0];

  fs.writeFileSync(
    deployedAddressesPath,
    JSON.stringify(deployedData, null, 2)
  );
  
  console.log(`✅ Saved to: ${deployedAddressesPath}\n`);

  // Summary
  console.log("=" .repeat(60));
  console.log("🎉 DEPLOYMENT COMPLETE!");
  console.log("=" .repeat(60));
  console.log(`📍 QuoterV2 Address: ${quoterV2Address}`);
  console.log(`🌐 Network: ${network} (Chain ID: ${hre.network.config.chainId})`);
  console.log(`⛽ Deployer: ${deployer.address}`);
  console.log("=" .repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
