import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("=== Deploying GraduationController V6 with CORRECT Kaspa Finance Addresses ===\n");
  
  // Load deployed addresses
  const registry = JSON.parse(fs.readFileSync('contracts/deployed_addresses.json', 'utf8'));
  
  const KF_FACTORY = registry.externalContracts.KaspaFinance.Factory;
  const KF_POSITION_MGR = registry.externalContracts.KaspaFinance.PositionManager;
  const KF_WKAS = registry.externalContracts.KaspaFinance.WKAS;
  const ORACLE = registry.wallets.Oracle;
  const TREASURY = registry.wallets.Treasury;
  
  // Use current TokenFactory V7 temporarily (will deploy new V8 after)
  const TEMP_TF = registry.contracts.TokenFactory.address;
  
  console.log("Constructor params:");
  console.log(`  Factory:        ${KF_FACTORY}`);
  console.log(`  Position Mgr:   ${KF_POSITION_MGR}`);
  console.log(`  WKAS:           ${KF_WKAS}`);
  console.log(`  Oracle:         ${ORACLE}`);
  console.log(`  TokenFactory:   ${TEMP_TF} (temp, will update)`);
  console.log(`  Treasury:       ${TREASURY}`);
  
  console.log("\nDeploying GraduationControllerV3 (actually V6)...");
  
  const GC = await hre.ethers.getContractFactory("GraduationControllerV3");
  const gc = await GC.deploy(
    KF_FACTORY,
    KF_POSITION_MGR,
    KF_WKAS,
    ORACLE,
    TEMP_TF,
    TREASURY
  );
  
  await gc.waitForDeployment();
  const gcAddress = await gc.getAddress();
  
  console.log(`\n✅ GraduationController V6 deployed: ${gcAddress}`);
  console.log(`   TX: ${gc.deploymentTransaction().hash}`);
  
  // Update registry
  registry.contracts.GraduationController = {
    version: "V6",
    address: gcAddress,
    deployedAt: new Date().toISOString().split('T')[0],
    notes: "FIXED: Correct Kaspa Finance testnet addresses from working LP tx"
  };
  
  fs.writeFileSync(
    'contracts/deployed_addresses.json',
    JSON.stringify(registry, null, 2)
  );
  
  console.log(`\n✅ Updated deployed_addresses.json`);
  console.log(`\nNEXT STEPS:`);
  console.log(`  1. Deploy TokenFactory V8 referencing this GC`);
  console.log(`  2. Call GC.setTokenFactory() to update from 0x0000... to new TF`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
