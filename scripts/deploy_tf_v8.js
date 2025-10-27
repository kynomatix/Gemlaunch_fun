import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("=== Deploying TokenFactory V8 with GraduationController V6 ===\n");
  
  // Load deployed addresses
  const registry = JSON.parse(fs.readFileSync('contracts/deployed_addresses.json', 'utf8'));
  
  const GC_V6 = registry.contracts.GraduationController.address;
  const TREASURY = registry.wallets.Treasury;
  const ORACLE = registry.wallets.Oracle;
  
  // For testnet, use unique placeholder addresses (TokenFactory requires all wallets to be unique)
  const [deployer] = await hre.ethers.getSigners();
  const AIRDROP_TREASURY = deployer.address; // Use deployer
  const PLATFORM_DEV = "0xA51d8F597570353aE50A25df90aDe162D2305FfA"; // User wallet
  const ADMIN = ORACLE;
  const BUYBACK_RESERVE = "0x0000000000000000000000000000000000000001"; // Placeholder
  const KASPA_SUPPORT = "0x0000000000000000000000000000000000000002"; // Placeholder
  const COMMUNITY_REWARDS = "0x0000000000000000000000000000000000000003"; // Placeholder
  
  console.log("Constructor params:");
  console.log(`  GraduationController:   ${GC_V6}`);
  console.log(`  Treasury:               ${TREASURY}`);
  console.log(`  AirdropTreasury:        ${AIRDROP_TREASURY}`);
  console.log(`  PlatformDevelopment:    ${PLATFORM_DEV}`);
  console.log(`  Oracle:                 ${ORACLE}`);
  console.log(`  Admin:                  ${ADMIN}`);
  console.log(`  BuybackReserve:         ${BUYBACK_RESERVE}`);
  console.log(`  KaspaSupport:           ${KASPA_SUPPORT}`);
  console.log(`  CommunityRewards:       ${COMMUNITY_REWARDS}`);
  
  console.log("\nDeploying TokenFactory...");
  
  const TF = await hre.ethers.getContractFactory("TokenFactory");
  const tf = await TF.deploy(
    GC_V6,
    TREASURY,
    AIRDROP_TREASURY,
    PLATFORM_DEV,
    ORACLE,
    ADMIN,
    BUYBACK_RESERVE,
    KASPA_SUPPORT,
    COMMUNITY_REWARDS
  );
  
  await tf.waitForDeployment();
  const tfAddress = await tf.getAddress();
  
  console.log(`\n✅ TokenFactory V8 deployed: ${tfAddress}`);
  console.log(`   TX: ${tf.deploymentTransaction().hash}`);
  
  // Update registry
  registry.contracts.TokenFactory = {
    version: "V8",
    address: tfAddress,
    deployedAt: new Date().toISOString().split('T')[0],
    notes: "References GC V6 with correct Kaspa Finance addresses"
  };
  
  fs.writeFileSync(
    'contracts/deployed_addresses.json',
    JSON.stringify(registry, null, 2)
  );
  
  console.log(`\n✅ Updated deployed_addresses.json`);
  console.log(`\nNEXT STEPS:`);
  console.log(`  1. Call GC.setTokenFactory(${tfAddress}) to complete the link`);
  console.log(`  2. Update web3_service.py constants`);
  console.log(`  3. Deploy test token to verify graduation works`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
