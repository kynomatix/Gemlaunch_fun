import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("=== Deploying TokenFactory V9 with BondingCurvePool Graduation Fix ===\n");
  
  // Load deployed addresses
  const registry = JSON.parse(fs.readFileSync('contracts/deployed_addresses.json', 'utf8'));
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying from:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "KAS\n");
  
  // Use addresses from registry
  const GC_V6 = registry.contracts.GraduationController.address;
  const TREASURY = registry.wallets.Treasury;
  const ORACLE = registry.wallets.Oracle;
  
  // NOTE: TokenFactory requires treasury != admin, treasury != oracle, airdropTreasury != platformDev
  const AIRDROP_TREASURY = TREASURY;
  const PLATFORM_DEV_WALLET = ORACLE; // Use oracle (different from airdrop treasury)
  const GRADUATION_ORACLE = ORACLE;
  const ADMIN = ORACLE; // Use oracle as admin (different from treasury)
  const BUYBACK_RESERVE = TREASURY;
  const KASPA_NETWORK_SUPPORT = TREASURY;
  const COMMUNITY_REWARDS = TREASURY;
  
  console.log("📋 Configuration:");
  console.log("  GraduationController V6:", GC_V6);
  console.log("  Graduation Oracle:", GRADUATION_ORACLE);
  console.log("  Treasury:", TREASURY);
  console.log("  Admin:", ADMIN);
  console.log("");
  
  // Deploy TokenFactory V9
  console.log("Deploying TokenFactory V9 with fixed BondingCurvePool...");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const factory = await TokenFactory.deploy(
    GC_V6,                    // 1. graduationController
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
  
  console.log("✅ TokenFactory V9 deployed:", factoryAddress);
  console.log(`   TX: ${factory.deploymentTransaction().hash}`);
  console.log("");
  
  // Update deployment registry
  registry.contracts.TokenFactory = {
    version: "V9",
    address: factoryAddress,
    deployedAt: new Date().toISOString().split('T')[0],
    notes: "CRITICAL FIX: Added graduationController to _update() exemptions - allows GC to receive 25% LP supply"
  };
  
  fs.writeFileSync(
    'contracts/deployed_addresses.json',
    JSON.stringify(registry, null, 2)
  );
  
  console.log("✅ Updated deployed_addresses.json");
  console.log("");
  
  // Next steps
  console.log("📌 NEXT STEPS:");
  console.log("1. ✅ deployed_addresses.json updated automatically");
  console.log("2. Update services/web3_service.py TOKEN_FACTORY_ADDRESS constant");
  console.log("3. Run scripts/link_gc_tf.js to link GC V6 ↔ TF V9");
  console.log("4. Run scripts/validate_tf_gc_linkage.js to verify linkage");
  console.log("5. Create test token and verify graduation ACTUALLY works");
  console.log("");
  console.log("⚠️  Remember: This is the FIX for the STF error. Test it thoroughly!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
