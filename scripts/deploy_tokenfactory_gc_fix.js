import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("🚀 Deploying TokenFactory with GraduationController initialization fix...");
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer address:", deployer.address);
  
  // Use same constructor params as V4 deployment
  const config = {
    graduationController: "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89",
    treasury: "0xe281e4776FB5De20817D0bbC72B0C4b955565619",
    airdropTreasury: "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",
    platformDevelopmentWallet: "0xe281e4776FB5De20817D0bbC72B0C4b955565619",
    graduationOracle: "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",
    admin: "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",
    buybackReserveWallet: "0xe281e4776FB5De20817D0bbC72B0C4b955565619",
    kaspaNetworkSupportWallet: "0xe281e4776FB5De20817D0bbC72B0C4b955565619",
    communityRewardsWallet: "0xe281e4776FB5De20817D0bbC72B0C4b955565619"
  };
  
  console.log("\n📋 Constructor Parameters:");
  console.log("  GraduationController:", config.graduationController);
  console.log("  Treasury:", config.treasury);
  console.log("  AirdropTreasury:", config.airdropTreasury);
  console.log("  PlatformDevelopmentWallet:", config.platformDevelopmentWallet);
  console.log("  GraduationOracle:", config.graduationOracle);
  console.log("  Admin:", config.admin);
  console.log("  BuybackReserveWallet:", config.buybackReserveWallet);
  console.log("  KaspaNetworkSupportWallet:", config.kaspaNetworkSupportWallet);
  console.log("  CommunityRewardsWallet:", config.communityRewardsWallet);
  
  // Deploy TokenFactory (VestingDeployer is auto-deployed in constructor)
  console.log("\n📦 Deploying TokenFactory...");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const tokenFactory = await TokenFactory.deploy(
    config.graduationController,
    config.treasury,
    config.airdropTreasury,
    config.platformDevelopmentWallet,
    config.graduationOracle,
    config.admin,
    config.buybackReserveWallet,
    config.kaspaNetworkSupportWallet,
    config.communityRewardsWallet
  );
  
  await tokenFactory.waitForDeployment();
  const tokenFactoryAddress = await tokenFactory.getAddress();
  const deployTx = tokenFactory.deploymentTransaction();
  
  console.log("✅ TokenFactory deployed to:", tokenFactoryAddress);
  console.log("   Transaction hash:", deployTx.hash);
  console.log("   Block number:", deployTx.blockNumber);
  
  // Wait for confirmations
  console.log("\n⏳ Waiting for confirmations...");
  await deployTx.wait(2);
  console.log("✅ Confirmed!");
  
  // Get VestingDeployer address (auto-deployed by TokenFactory)
  console.log("\n🔍 Reading VestingDeployer address...");
  const vestingDeployerAddress = await tokenFactory.vestingDeployer();
  console.log("  VestingDeployer address:", vestingDeployerAddress);
  
  // Verify GraduationController is set correctly
  console.log("\n🔍 Verifying configuration...");
  const gcAddress = await tokenFactory.graduationController();
  const goAddress = await tokenFactory.graduationOracle();
  console.log("  GraduationController address:", gcAddress);
  console.log("  GraduationOracle address:", goAddress);
  
  if (gcAddress.toLowerCase() === config.graduationController.toLowerCase()) {
    console.log("  ✅ GraduationController set correctly");
  } else {
    console.log("  ❌ ERROR: GraduationController mismatch!");
  }
  
  if (goAddress.toLowerCase() === config.graduationOracle.toLowerCase()) {
    console.log("  ✅ GraduationOracle set correctly");
  } else {
    console.log("  ❌ ERROR: GraduationOracle mismatch!");
  }
  
  // Save deployment info
  const deploymentInfo = {
    deployment_date: new Date().toISOString().split('T')[0],
    deployment_timestamp: Math.floor(Date.now() / 1000),
    network: "kasplex_testnet",
    chain_id: 167012,
    version: "GC_INIT_FIX",
    fix_description: "Added _graduationController parameter to BondingCurvePool constructor to ensure GC address is set during deployment",
    contracts: {
      TokenFactory: {
        address: tokenFactoryAddress,
        tx_hash: deployTx.hash,
        block: deployTx.blockNumber,
        deployer: deployer.address
      },
      VestingDeployer: {
        address: vestingDeployerAddress,
        deployer: deployer.address
      }
    },
    constructor_params: config,
    changes: [
      "BondingCurvePool: Added _graduationController parameter to constructor",
      "BondingCurvePool: Added require(_graduationController != address(0)) validation",
      "BondingCurvePool: Added graduationController = _graduationController assignment",
      "TokenFactory: Now passes both graduationOracle AND graduationController to pool constructor"
    ],
    references: {
      graduationController: config.graduationController,
      previous_tokenfactory: "0x408dcf382d38eCe30b2b25C86440f923CAa7B631"
    }
  };
  
  const filename = `deployments/tokenfactory_gc_init_fix_${Date.now()}.json`;
  fs.writeFileSync(filename, JSON.stringify(deploymentInfo, null, 2));
  console.log("\n💾 Deployment info saved to:", filename);
  
  console.log("\n🎉 Deployment complete!");
  console.log("\n📝 Next steps:");
  console.log("  1. Update backend TOKEN_FACTORY_ADDRESS to:", tokenFactoryAddress);
  console.log("  2. Update backend VESTING_DEPLOYER_ADDRESS to:", vestingDeployerAddress);
  console.log("  3. Restart application");
  console.log("  4. Create test token and verify graduationController is set");
  console.log("  5. Fund token to >$50 and test graduation flow");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
