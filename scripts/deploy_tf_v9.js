import hre from "hardhat";

async function main() {
  console.log("🚀 Deploying TokenFactory V9 with BondingCurvePool graduation fix...\n");
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying from:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "KAS\n");
  
  // GraduationController V6 address (with correct Kaspa Finance addresses)
  const graduationControllerV6 = "0xBbfdF7341aaF104D259876972844EBF9795b9C4C";
  
  // Platform addresses (checksummed for Kasplex testnet)
  // NOTE: TokenFactory requires treasury != admin, treasury != oracle, airdropTreasury != platformDev
  const TREASURY = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";
  const AIRDROP_TREASURY = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";
  const PLATFORM_DEV_WALLET = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"; // Oracle wallet (different from airdrop)
  const GRADUATION_ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
  const ADMIN = deployer.address; // Use deployer as admin (different from treasury)
  const BUYBACK_RESERVE = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";
  const KASPA_NETWORK_SUPPORT = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";
  const COMMUNITY_REWARDS = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";
  
  console.log("📋 Configuration:");
  console.log("  GraduationController V6:", graduationControllerV6);
  console.log("  Graduation Oracle:", GRADUATION_ORACLE);
  console.log("  Treasury:", TREASURY);
  console.log("");
  
  // Deploy TokenFactory V9
  console.log("Deploying TokenFactory V9...");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const factory = await TokenFactory.deploy(
    TREASURY,
    AIRDROP_TREASURY,
    PLATFORM_DEV_WALLET,
    GRADUATION_ORACLE,
    graduationControllerV6,
    ADMIN,
    BUYBACK_RESERVE,
    KASPA_NETWORK_SUPPORT,
    COMMUNITY_REWARDS
  );
  
  await factory.waitForDeployment();
  const factoryAddress = await factory.getAddress();
  
  console.log("✅ TokenFactory V9 deployed:", factoryAddress);
  console.log("");
  
  // Update deployment registry
  console.log("📝 Update contracts/deployed_addresses.json:");
  console.log(`  "TokenFactory": "${factoryAddress}",`);
  console.log("");
  
  // Next steps
  console.log("📌 NEXT STEPS:");
  console.log("1. Update contracts/deployed_addresses.json with TokenFactory V9 address");
  console.log("2. Update services/web3_service.py TOKEN_FACTORY_ADDRESS constant");
  console.log("3. Run scripts/link_gc_tf.js to link GC V6 ↔ TF V9");
  console.log("4. Run scripts/validate_tf_gc_linkage.js to verify linkage");
  console.log("5. Create test token and verify graduation works");
  console.log("");
  console.log("✅ TokenFactory V9 deployment complete!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
