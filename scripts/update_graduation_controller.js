import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Update TokenFactory's graduationController to the actual GraduationController address
 */
async function main() {
  console.log("\n🔧 Updating TokenFactory graduationController...\n");
  console.log("=" .repeat(80));
  
  // Load deployment info
  const factoryDeploymentPath = path.join(process.cwd(), "deployments", "kasplex_testnet_factory.json");
  const graduationDeploymentPath = path.join(process.cwd(), "deployments", "kasplex_testnet_graduation.json");
  
  if (!fs.existsSync(factoryDeploymentPath)) {
    throw new Error(`Factory deployment file not found: ${factoryDeploymentPath}`);
  }
  
  if (!fs.existsSync(graduationDeploymentPath)) {
    throw new Error(`Graduation deployment file not found: ${graduationDeploymentPath}`);
  }
  
  const factoryDeployment = JSON.parse(fs.readFileSync(factoryDeploymentPath, "utf8"));
  const graduationDeployment = JSON.parse(fs.readFileSync(graduationDeploymentPath, "utf8"));
  
  const factoryAddress = factoryDeployment.tokenFactory;
  const graduationControllerAddress = graduationDeployment.graduationController;
  
  console.log("\n📋 Configuration:");
  console.log("   TokenFactory:", factoryAddress);
  console.log("   GraduationController:", graduationControllerAddress);
  
  // Get deployer
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  
  console.log("\n💼 Deployer:");
  console.log("   Address:", deployerAddress);
  
  // Get TokenFactory contract
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const tokenFactory = TokenFactory.attach(factoryAddress);
  
  // Check current graduationController
  const currentController = await tokenFactory.graduationController();
  console.log("\n🔍 Current graduationController:", currentController);
  
  if (currentController.toLowerCase() === graduationControllerAddress.toLowerCase()) {
    console.log("   ✅ Already set to correct address!");
    return;
  }
  
  console.log("\n🚀 Updating graduationController...");
  const tx = await tokenFactory.setGraduationController(graduationControllerAddress);
  console.log("   ✓ Transaction sent!");
  console.log("   Tx hash:", tx.hash);
  console.log("   Waiting for confirmation...");
  
  await tx.wait();
  console.log("   ✓ Transaction confirmed!");
  
  // Verify update
  const updatedController = await tokenFactory.graduationController();
  console.log("\n✅ Updated graduationController:", updatedController);
  
  if (updatedController.toLowerCase() !== graduationControllerAddress.toLowerCase()) {
    throw new Error("❌ Update failed - address mismatch!");
  }
  
  console.log("\n" + "=".repeat(80));
  console.log("✅ GRADUATION CONTROLLER UPDATE COMPLETE");
  console.log("=".repeat(80));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
