import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("=== Deploying TokenFactory V10 with Direct Token Transfer Fix ===\n");
  
  // Load deployed addresses (path relative to where hardhat runs from)
  const registryPath = process.cwd().includes('/contracts') 
    ? '../contracts/deployed_addresses.json' 
    : 'contracts/deployed_addresses.json';
  const registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying from:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "KAS\n");
  
  // Use addresses from registry - GC V7 should be set before running this
  const GC_V7 = registry.contracts.GraduationController.address;
  const TREASURY = registry.wallets.Treasury;
  const ORACLE = registry.wallets.Oracle;
  
  console.log("🔍 Verifying GraduationController V7 is set...");
  if (!GC_V7 || GC_V7 === "0xBbfdF7341aaF104D259876972844EBF9795b9C4C") {
    console.error("❌ ERROR: GraduationController V7 not found in registry!");
    console.error("   Please deploy GC V7 first and update deployed_addresses.json");
    process.exit(1);
  }
  
  // NOTE: TokenFactory requires treasury != admin, treasury != oracle, airdropTreasury != platformDev
  const AIRDROP_TREASURY = TREASURY;
  const PLATFORM_DEV_WALLET = ORACLE; // Use oracle (different from airdrop treasury)
  const GRADUATION_ORACLE = ORACLE;
  const ADMIN = ORACLE; // Use oracle as admin (different from treasury)
  const BUYBACK_RESERVE = TREASURY;
  const KASPA_NETWORK_SUPPORT = TREASURY;
  const COMMUNITY_REWARDS = TREASURY;
  
  console.log("📋 Configuration:");
  console.log("  GraduationController V7:", GC_V7);
  console.log("  Graduation Oracle:", GRADUATION_ORACLE);
  console.log("  Treasury:", TREASURY);
  console.log("  Admin:", ADMIN);
  console.log("");
  
  // Deploy TokenFactory V10
  console.log("Deploying TokenFactory V10...");
  console.log("  V10 FIX: Pool transfers tokens directly to GC during initiation");
  console.log("  No more approve/transferFrom - bypasses STF error completely");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const factory = await TokenFactory.deploy(
    GC_V7,                    // 1. graduationController (V7)
    TREASURY,                 // 2. treasury
    AIRDROP_TREASURY,         // 3. airdropTreasury
    PLATFORM_DEV_WALLET,      // 4. platformDevelopmentWallet
    GRADUATION_ORACLE,        // 5. graduationOracle
    ADMIN,                    // 6. admin
    BUYBACK_RESERVE,          // 7. buybackReserve
    KASPA_NETWORK_SUPPORT,    // 8. kaspaSupport
    COMMUNITY_REWARDS         // 9. communityRewards
  );
  
  await factory.waitForDeployment();
  const factoryAddress = await factory.getAddress();
  
  console.log("✅ TokenFactory V10 deployed:", factoryAddress);
  console.log(`   TX: ${factory.deploymentTransaction().hash}`);
  console.log("");
  
  // Update deployment registry
  registry.contracts.TokenFactory = {
    version: "V10",
    address: factoryAddress,
    deployedAt: new Date().toISOString().split('T')[0],
    notes: "V10 FIX: Pool uses _transfer() to push tokens to GC during initiation (no approve/transferFrom)"
  };
  
  fs.writeFileSync(
    registryPath,
    JSON.stringify(registry, null, 2)
  );
  
  console.log("✅ Updated deployed_addresses.json");
  console.log("");
  
  // Next steps
  console.log("📌 NEXT STEPS:");
  console.log("1. ✅ deployed_addresses.json updated automatically");
  console.log("2. Update services/web3_service.py constants:");
  console.log(`   TOKEN_FACTORY_ADDRESS = "${factoryAddress}"`);
  console.log(`   GRADUATION_CONTROLLER_ADDRESS = "${GC_V7}"`);
  console.log("3. Run scripts/link_gc_tf.js to link GC V7 ↔ TF V10");
  console.log("4. Run scripts/validate_tf_gc_linkage.js to verify linkage");
  console.log("5. Create test token and verify graduation WORKS!");
  console.log("");
  console.log("🎯 This should FINALLY fix the STF error by avoiding approve/transferFrom entirely!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
