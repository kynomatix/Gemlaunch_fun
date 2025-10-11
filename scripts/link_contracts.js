import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Load deployment info from JSON file
 */
function loadDeployment(network, contractType) {
  const deploymentsDir = path.join(process.cwd(), "deployments");
  const deploymentFile = path.join(deploymentsDir, `${network}_${contractType}.json`);
  
  if (!fs.existsSync(deploymentFile)) {
    throw new Error(`Deployment file not found: ${deploymentFile}`);
  }
  
  return JSON.parse(fs.readFileSync(deploymentFile, "utf8"));
}

async function main() {
  console.log("\n🔗 Linking GraduationController to TokenFactory...\n");
  console.log("=" .repeat(80));
  
  // Get network
  const network = hre.network.name;
  console.log("Network:", network);
  
  // Load deployment info
  console.log("\n📋 Loading Deployment Info...");
  const factoryDeployment = loadDeployment(network, "factory");
  const graduationDeployment = loadDeployment(network, "graduation");
  
  const factoryAddress = factoryDeployment.tokenFactory;
  const graduationControllerAddress = graduationDeployment.graduationController;
  
  console.log("   ✓ TokenFactory address:", factoryAddress);
  console.log("   ✓ GraduationController address:", graduationControllerAddress);
  
  // Validate addresses are non-zero
  if (factoryAddress === hre.ethers.ZeroAddress) {
    throw new Error("TokenFactory address is zero address!");
  }
  if (graduationControllerAddress === hre.ethers.ZeroAddress) {
    throw new Error("GraduationController address is zero address!");
  }
  
  // Get deployer (owner of TokenFactory)
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  const balance = await hre.ethers.provider.getBalance(deployerAddress);
  
  console.log("\n💼 Current Signer:");
  console.log("   Address:", deployerAddress);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS");
  console.log("   Note: Signer must be TokenFactory owner to execute this transaction")
  
  if (balance === 0n) {
    throw new Error("❌ Deployer wallet has no KAS for gas!");
  }
  
  // Get TokenFactory contract instance
  console.log("\n📄 Loading TokenFactory Contract...");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const tokenFactory = TokenFactory.attach(factoryAddress);
  
  // Verify current state
  console.log("\n🔍 Checking Current State...");
  const currentGraduationController = await tokenFactory.graduationController();
  const owner = await tokenFactory.owner();
  
  console.log("   Current graduationController:", currentGraduationController);
  console.log("   TokenFactory owner:", owner);
  
  // Verify owner matches deployer
  if (owner !== deployerAddress) {
    throw new Error("❌ Deployer is not the owner of TokenFactory!");
  }
  
  // Check if already updated
  if (currentGraduationController === graduationControllerAddress) {
    console.log("\n✅ GraduationController is already linked correctly!");
    console.log("   No update needed.");
    
    // Still verify permissions even if already linked
    console.log("\n🔐 Verifying GraduationController Permissions...");
    const GraduationController = await hre.ethers.getContractFactory("GraduationController");
    const graduationController = GraduationController.attach(graduationControllerAddress);
    
    const gcOwner = await graduationController.owner();
    const gcOracle = await graduationController.graduationOracle();
    const expectedOracle = graduationDeployment.wallets?.secondary?.address;
    
    console.log("   GraduationController.owner():", gcOwner);
    console.log("   GraduationController.graduationOracle():", gcOracle);
    console.log("   Expected oracle (from deployment):", expectedOracle || "N/A");
    
    // Enforce permission validation
    if (expectedOracle && gcOracle !== expectedOracle) {
      throw new Error(
        `GraduationController oracle mismatch!\n` +
        `   Expected: ${expectedOracle}\n` +
        `   Actual: ${gcOracle}\n` +
        `   The GraduationController is misconfigured.`
      );
    }
    
    const expectedOwner = graduationDeployment.deployer;
    if (expectedOwner && gcOwner !== expectedOwner) {
      console.warn(`   ⚠️  Warning: GraduationController owner (${gcOwner}) differs from deployer (${expectedOwner})`);
      console.warn(`   This may indicate ownership transfer or misconfiguration`);
    }
    
    console.log("   ✓ Oracle address matches deployment configuration!");
    console.log("   ✓ GraduationController permissions verified!");
    console.log("\n" + "=" .repeat(80));
    return;
  }
  
  console.log("   ⚠️  Current graduationController:", currentGraduationController);
  console.log("   ✓  Will update to:", graduationControllerAddress);
  
  // Estimate gas for the transaction
  console.log("\n⛽ Estimating Gas...");
  try {
    const gasEstimate = await tokenFactory.setGraduationController.estimateGas(
      graduationControllerAddress
    );
    const feeData = await hre.ethers.provider.getFeeData();
    
    console.log("   Estimated gas:", gasEstimate.toString());
    console.log("   Gas price:", feeData.gasPrice?.toString() || "auto");
    
    const estimatedCost = gasEstimate * (feeData.gasPrice || 0n);
    console.log("   Estimated cost:", hre.ethers.formatEther(estimatedCost), "KAS");
  } catch (error) {
    console.error("   ⚠️  Gas estimation failed:", error.message);
  }
  
  // Execute the update
  console.log("\n🔄 Updating GraduationController Address...");
  console.log("=" .repeat(80));
  
  try {
    const tx = await tokenFactory.setGraduationController(graduationControllerAddress);
    
    console.log("   ✓ Transaction sent!");
    console.log("   Tx hash:", tx.hash);
    console.log("   Waiting for confirmation...");
    
    const receipt = await tx.wait();
    
    console.log("\n✅ Transaction Confirmed!");
    console.log("   Block number:", receipt.blockNumber);
    console.log("   Gas used:", receipt.gasUsed.toString());
    console.log("   Status:", receipt.status === 1 ? "Success" : "Failed");
    
    if (receipt.status !== 1) {
      throw new Error("Transaction failed!");
    }
    
    // Verify the update
    console.log("\n🔍 Verifying Update...");
    const updatedGraduationController = await tokenFactory.graduationController();
    
    console.log("   Previous address:", currentGraduationController);
    console.log("   New address:", updatedGraduationController);
    
    if (updatedGraduationController === graduationControllerAddress) {
      console.log("   ✓ TokenFactory.graduationController() verification successful!");
    } else {
      throw new Error("Verification failed! Address mismatch.");
    }
    
    // Verify GraduationController permissions
    console.log("\n🔐 Verifying GraduationController Permissions...");
    const GraduationController = await hre.ethers.getContractFactory("GraduationController");
    const graduationController = GraduationController.attach(graduationControllerAddress);
    
    const gcOwner = await graduationController.owner();
    const gcOracle = await graduationController.graduationOracle();
    const expectedOracle = graduationDeployment.wallets?.secondary?.address;
    
    console.log("   GraduationController.owner():", gcOwner);
    console.log("   GraduationController.graduationOracle():", gcOracle);
    console.log("   Expected oracle (from deployment):", expectedOracle || "N/A");
    
    // Enforce permission validation
    if (expectedOracle && gcOracle !== expectedOracle) {
      throw new Error(
        `GraduationController oracle mismatch!\n` +
        `   Expected: ${expectedOracle}\n` +
        `   Actual: ${gcOracle}\n` +
        `   The GraduationController is misconfigured.`
      );
    }
    
    // Verify owner is deployer (for controlled deployment)
    const expectedOwner = graduationDeployment.deployer;
    if (expectedOwner && gcOwner !== expectedOwner) {
      console.warn(`   ⚠️  Warning: GraduationController owner (${gcOwner}) differs from deployer (${expectedOwner})`);
      console.warn(`   This may indicate ownership transfer or misconfiguration`);
    }
    
    console.log("   ✓ Oracle address matches deployment configuration!");
    console.log("   ✓ GraduationController permissions verified!")
    
    // Check for events
    console.log("\n📡 Transaction Events:");
    if (receipt.logs && receipt.logs.length > 0) {
      console.log("   Found", receipt.logs.length, "event(s)");
      
      // Try to parse GraduationControllerUpdated event
      receipt.logs.forEach((log, index) => {
        try {
          const parsedLog = tokenFactory.interface.parseLog({
            topics: [...log.topics],
            data: log.data
          });
          
          if (parsedLog && parsedLog.name === "GraduationControllerUpdated") {
            console.log(`   Event ${index + 1}: GraduationControllerUpdated`);
            console.log("      newController:", parsedLog.args.newController);
          }
        } catch (e) {
          // Ignore parsing errors for other events
        }
      });
    } else {
      console.log("   No events found");
    }
    
    // Save linking info
    const linkingInfo = {
      network: network,
      chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
      tokenFactory: factoryAddress,
      graduationController: graduationControllerAddress,
      previousGraduationController: currentGraduationController,
      linkedBy: deployerAddress,
      linkingTx: tx.hash,
      blockNumber: receipt.blockNumber,
      gasUsed: receipt.gasUsed.toString(),
      timestamp: new Date().toISOString()
    };
    
    const deploymentsDir = path.join(process.cwd(), "deployments");
    const linkingFile = path.join(deploymentsDir, `${network}_linking.json`);
    fs.writeFileSync(linkingFile, JSON.stringify(linkingInfo, null, 2));
    console.log("\n💾 Linking Info Saved:", linkingFile);
    
    // Display summary
    console.log("\n📊 Linking Summary:");
    console.log("=" .repeat(80));
    console.log("   ✓ TokenFactory:", factoryAddress);
    console.log("   ✓ GraduationController:", graduationControllerAddress);
    console.log("   ✓ Link verified successfully");
    console.log("   ✓ System ready for token graduation");
    
    console.log("\n📌 Next Steps:");
    console.log("=" .repeat(80));
    console.log("   1. ✓ TokenFactory and GraduationController linked");
    console.log("   2. Deploy test token via TokenFactory");
    console.log("   3. Test token trading and bonding curve");
    console.log("   4. Test graduation flow when threshold is reached");
    
    console.log("\n" + "=" .repeat(80));
    console.log("✅ LINKING COMPLETE - CONTRACTS ARE CONNECTED");
    console.log("=" .repeat(80) + "\n");
    
  } catch (error) {
    console.error("\n❌ Linking Failed!");
    console.error("=" .repeat(80));
    console.error("Error:", error.message);
    
    if (error.message.includes("Ownable: caller is not the owner")) {
      console.error("\n⚠️  Only the TokenFactory owner can update the graduation controller");
      console.error("   Current owner:", owner);
      console.error("   Your address:", deployerAddress);
    }
    
    throw error;
  }
}

// Execute linking
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
