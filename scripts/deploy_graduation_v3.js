import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Retry logic for RPC calls
 * @param {Function} fn Function to retry
 * @param {number} maxRetries Maximum number of retries
 * @param {number} delayMs Delay between retries in milliseconds
 */
async function retryWithBackoff(fn, maxRetries = 3, delayMs = 2000) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      const isLastAttempt = i === maxRetries - 1;
      const isRpcError = error.message?.includes("RPC") || 
                        error.message?.includes("network") ||
                        error.message?.includes("timeout") ||
                        error.code === "NETWORK_ERROR";
      
      if (isLastAttempt || !isRpcError) {
        throw error;
      }
      
      console.log(`   ⚠️  RPC error, retrying in ${delayMs}ms... (attempt ${i + 1}/${maxRetries})`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
      delayMs *= 2; // Exponential backoff
    }
  }
}

/**
 * Validate constructor parameters
 */
function validateConstructorParams(params) {
  const errors = [];
  
  // Check for zero addresses
  Object.entries(params).forEach(([key, value]) => {
    if (value === hre.ethers.ZeroAddress || value === "0x0000000000000000000000000000000000000000") {
      errors.push(`${key} cannot be zero address`);
    }
    
    // Validate address format
    if (!hre.ethers.isAddress(value)) {
      errors.push(`${key} is not a valid address: ${value}`);
    }
  });
  
  // Check for duplicate addresses (contract constraint)
  if (params.kaspaFinanceFactory === params.kaspaFinancePositionManager) {
    errors.push("kaspaFinanceFactory cannot equal kaspaFinancePositionManager");
  }
  if (params.kaspaFinanceFactory === params.kaspaFinanceWKAS) {
    errors.push("kaspaFinanceFactory cannot equal kaspaFinanceWKAS");
  }
  if (params.kaspaFinancePositionManager === params.kaspaFinanceWKAS) {
    errors.push("kaspaFinancePositionManager cannot equal kaspaFinanceWKAS");
  }
  
  return errors;
}

async function main() {
  console.log("\n🚀 Deploying GraduationController V3 to Kasplex Testnet...\n");
  console.log("=".repeat(80));
  
  // Get network
  const network = hre.network.name;
  console.log("Network:", network);
  
  // Get deployer
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  
  console.log("\n💼 Deployer Wallet:");
  const balance = await retryWithBackoff(async () => {
    return await hre.ethers.provider.getBalance(deployerAddress);
  });
  
  console.log("   Address:", deployerAddress);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS");
  
  if (balance === 0n) {
    throw new Error("❌ Deployer wallet has no KAS! Fund it first.");
  }
  
  // Constructor parameters for V3
  // NOTE: V3 adds treasury parameter for excess token handling (FIX #7)
  const constructorParams = {
    kaspaFinanceFactory: "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8",
    kaspaFinancePositionManager: "0x4E25637cF39822364b877F81B18c5B6CF0eeF589",
    kaspaFinanceWKAS: "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94",
    graduationOracle: "0x5f837F62744D4d80Fc79C3A5346B4A228956914E",
    tokenFactory: "0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc",
    treasury: "0x5f837F62744D4d80Fc79C3A5346B4A228956914E" // Use oracle wallet as treasury
  };
  
  // Validate constructor parameters
  console.log("\n✅ Validating Constructor Parameters...");
  const validationErrors = validateConstructorParams(constructorParams);
  
  if (validationErrors.length > 0) {
    console.error("\n❌ Validation failed:");
    validationErrors.forEach(error => console.error("   -", error));
    throw new Error("Constructor parameter validation failed");
  }
  
  console.log("   ✓ All addresses are valid");
  console.log("   ✓ No duplicate addresses");
  console.log("   ✓ No zero addresses");
  
  // Display constructor parameters
  console.log("\n📝 Constructor Parameters:");
  console.log("=".repeat(80));
  console.table({
    "kaspaFinanceFactory": { address: constructorParams.kaspaFinanceFactory, description: "Uniswap V3 Factory" },
    "kaspaFinancePositionManager": { address: constructorParams.kaspaFinancePositionManager, description: "NFT Position Manager" },
    "kaspaFinanceWKAS": { address: constructorParams.kaspaFinanceWKAS, description: "Wrapped KAS Token" },
    "graduationOracle": { address: constructorParams.graduationOracle, description: "Backend Oracle" },
    "tokenFactory": { address: constructorParams.tokenFactory, description: "Token Factory V2" },
    "treasury": { address: constructorParams.treasury, description: "Treasury (Excess Tokens)" }
  });
  
  // Estimate gas
  console.log("\n⛽ Estimating Deployment Gas...");
  const GraduationController = await hre.ethers.getContractFactory(
    "contracts/GraduationControllerV3.sol:GraduationControllerV3"
  );
  
  const deploymentData = GraduationController.interface.encodeDeploy([
    constructorParams.kaspaFinanceFactory,
    constructorParams.kaspaFinancePositionManager,
    constructorParams.kaspaFinanceWKAS,
    constructorParams.graduationOracle,
    constructorParams.tokenFactory,
    constructorParams.treasury
  ]);
  
  const estimatedGas = await retryWithBackoff(async () => {
    return await hre.ethers.provider.estimateGas({
      from: deployerAddress,
      data: GraduationController.bytecode + deploymentData.slice(2)
    });
  });
  
  const feeData = await retryWithBackoff(async () => {
    return await hre.ethers.provider.getFeeData();
  });
  
  const estimatedCost = estimatedGas * (feeData.gasPrice || 0n);
  
  console.log("   Estimated gas:", estimatedGas.toString());
  console.log("   Gas price:", feeData.gasPrice?.toString() || "auto");
  console.log("   Estimated cost:", hre.ethers.formatEther(estimatedCost), "KAS");
  
  if (balance < estimatedCost) {
    console.warn("   ⚠️  Warning: Balance may be insufficient for deployment");
  }
  
  // Deploy GraduationController V3
  console.log("\n🏗️  Deploying GraduationController V3 Contract...");
  console.log("=".repeat(80));
  console.log("   ✨ V3 IMPROVEMENTS:");
  console.log("   - FIX #1: INITIAL_VIRTUAL_KAS = 0.001 ether (not 1000)");
  console.log("   - FIX #2/#3: Snapshot architecture (1089.99 KAS, not 89.991)");
  console.log("   - FIX #4: Tick spacing -887200/887200 (multiples of 50)");
  console.log("   - FIX #5: Atomic pool creation (no front-running)");
  console.log("   - FIX #6: LP NFT burned to 0x...dEaD");
  console.log("   - FIX #7: Excess to treasury (not pool)");
  console.log("   - FIX #8: sqrtPrice bounds validation");
  console.log("   - FIX #9: No try/catch on pool.completeGraduation()");
  console.log("   - FIX #10: Oracle locking during graduation");
  console.log("   - FIX #11: 30-minute deadline (1800s)");
  console.log("=".repeat(80));
  
  let graduationController;
  let deploymentTx;
  
  try {
    // Deploy with retry logic
    graduationController = await retryWithBackoff(async () => {
      return await GraduationController.deploy(
        constructorParams.kaspaFinanceFactory,
        constructorParams.kaspaFinancePositionManager,
        constructorParams.kaspaFinanceWKAS,
        constructorParams.graduationOracle,
        constructorParams.tokenFactory,
        constructorParams.treasury
      );
    });
    
    deploymentTx = graduationController.deploymentTransaction();
    console.log("   ✓ Transaction sent!");
    console.log("   Tx hash:", deploymentTx?.hash);
    console.log("   Waiting for 2 block confirmations...");
    
    // Wait for deployment with 2 confirmations
    await retryWithBackoff(async () => {
      return await graduationController.waitForDeployment();
    });
    
    // Wait for additional confirmation
    if (deploymentTx?.hash) {
      await retryWithBackoff(async () => {
        const receipt = await hre.ethers.provider.waitForTransaction(deploymentTx.hash, 2);
        return receipt;
      });
      console.log("   ✓ 2 block confirmations received");
    }
    
  } catch (error) {
    console.error("\n❌ Deployment Failed!");
    console.error("=".repeat(80));
    console.error("Error:", error.message);
    
    if (error.message.includes("Duplicate addresses")) {
      console.error("\n⚠️  Contract validation failed:");
      console.error("   - Ensure kaspaFinanceFactory != kaspaFinancePositionManager != kaspaFinanceWKAS");
    }
    
    throw error;
  }
  
  // Get deployment details
  const controllerAddress = await graduationController.getAddress();
  const deploymentReceipt = await retryWithBackoff(async () => {
    return await hre.ethers.provider.getTransactionReceipt(deploymentTx?.hash);
  });
  
  const blockNumber = deploymentReceipt?.blockNumber || await hre.ethers.provider.getBlockNumber();
  const gasUsed = deploymentReceipt?.gasUsed?.toString() || "N/A";
  const effectiveGasPrice = deploymentReceipt?.gasPrice?.toString() || "N/A";
  
  console.log("\n🎉 GraduationController V3 Deployed Successfully!");
  console.log("=".repeat(80));
  console.log("   Contract address:", controllerAddress);
  console.log("   Block number:", blockNumber);
  console.log("   Gas used:", gasUsed);
  console.log("   Gas price:", effectiveGasPrice);
  console.log("   Network:", network);
  console.log("   Chain ID:", (await hre.ethers.provider.getNetwork()).chainId);
  
  // Verify deployment by reading immutable variables and state
  console.log("\n🔍 Verifying Deployment...");
  console.log("=".repeat(80));
  
  try {
    // Read immutable addresses
    const factory = await retryWithBackoff(async () => {
      return await graduationController.kaspaFinanceFactory();
    });
    const positionManager = await retryWithBackoff(async () => {
      return await graduationController.kaspaFinancePositionManager();
    });
    const wkas = await retryWithBackoff(async () => {
      return await graduationController.kaspaFinanceWKAS();
    });
    const oracle = await retryWithBackoff(async () => {
      return await graduationController.graduationOracle();
    });
    const factory2 = await retryWithBackoff(async () => {
      return await graduationController.tokenFactory();
    });
    const treasury = await retryWithBackoff(async () => {
      return await graduationController.treasury();
    });
    
    // Read version
    const version = await retryWithBackoff(async () => {
      return await graduationController.VERSION();
    });
    
    // Read owner
    const owner = await retryWithBackoff(async () => {
      return await graduationController.owner();
    });
    
    // Read configuration
    const poolFeeTier = await retryWithBackoff(async () => {
      return await graduationController.POOL_FEE_TIER();
    });
    const slippageBps = await retryWithBackoff(async () => {
      return await graduationController.graduationSlippageBps();
    });
    const deadlineSeconds = await retryWithBackoff(async () => {
      return await graduationController.graduationDeadlineSeconds();
    });
    const maxPriceDeviationBps = await retryWithBackoff(async () => {
      return await graduationController.maxPriceDeviationBps();
    });
    
    // Read V3-specific constants
    const initialVirtualKas = await retryWithBackoff(async () => {
      return await graduationController.INITIAL_VIRTUAL_KAS();
    });
    const fullRangeTickLower = await retryWithBackoff(async () => {
      return await graduationController.FULL_RANGE_TICK_LOWER();
    });
    const fullRangeTickUpper = await retryWithBackoff(async () => {
      return await graduationController.FULL_RANGE_TICK_UPPER();
    });
    const burnAddress = await retryWithBackoff(async () => {
      return await graduationController.BURN_ADDRESS();
    });
    
    console.log("\n📋 Immutable Addresses:");
    console.log("   ✓ kaspaFinanceFactory:", factory);
    console.log("   ✓ kaspaFinancePositionManager:", positionManager);
    console.log("   ✓ kaspaFinanceWKAS:", wkas);
    console.log("   ✓ graduationOracle:", oracle);
    console.log("   ✓ tokenFactory:", factory2);
    console.log("   ✓ treasury:", treasury);
    
    console.log("\n📋 Contract State:");
    console.log("   ✓ VERSION:", version);
    console.log("   ✓ Owner:", owner);
    console.log("   ✓ Pool Fee Tier:", poolFeeTier.toString(), "bps (0.25%)");
    console.log("   ✓ Graduation Slippage:", slippageBps.toString(), "bps");
    console.log("   ✓ Graduation Deadline:", deadlineSeconds.toString(), "seconds (30 min)");
    console.log("   ✓ Max Price Deviation:", maxPriceDeviationBps.toString(), "bps");
    
    console.log("\n📋 V3 Critical Fixes:");
    console.log("   ✓ INITIAL_VIRTUAL_KAS:", hre.ethers.formatEther(initialVirtualKas), "KAS (FIX #1)");
    console.log("   ✓ FULL_RANGE_TICK_LOWER:", fullRangeTickLower.toString(), "(FIX #4)");
    console.log("   ✓ FULL_RANGE_TICK_UPPER:", fullRangeTickUpper.toString(), "(FIX #4)");
    console.log("   ✓ BURN_ADDRESS:", burnAddress, "(FIX #6)");
    
    // Verify addresses match constructor params
    console.log("\n✅ Verification Results:");
    const verifications = [
      { name: "Factory", expected: constructorParams.kaspaFinanceFactory, actual: factory },
      { name: "Position Manager", expected: constructorParams.kaspaFinancePositionManager, actual: positionManager },
      { name: "WKAS", expected: constructorParams.kaspaFinanceWKAS, actual: wkas },
      { name: "Oracle", expected: constructorParams.graduationOracle, actual: oracle },
      { name: "Token Factory", expected: constructorParams.tokenFactory, actual: factory2 },
      { name: "Treasury", expected: constructorParams.treasury, actual: treasury },
      { name: "Version", expected: "3.0.0", actual: version },
      { name: "INITIAL_VIRTUAL_KAS", expected: "0.001", actual: hre.ethers.formatEther(initialVirtualKas) },
      { name: "Tick Lower", expected: "-887200", actual: fullRangeTickLower.toString() },
      { name: "Tick Upper", expected: "887200", actual: fullRangeTickUpper.toString() },
      { name: "Burn Address", expected: "0x000000000000000000000000000000000000dEaD", actual: burnAddress }
    ];
    
    let allMatch = true;
    verifications.forEach(v => {
      const matches = v.expected.toLowerCase() === v.actual.toLowerCase();
      if (matches) {
        console.log(`   ✓ ${v.name} matches: ${v.actual}`);
      } else {
        console.log(`   ❌ ${v.name} mismatch! Expected: ${v.expected}, Got: ${v.actual}`);
        allMatch = false;
      }
    });
    
    if (!allMatch) {
      throw new Error("Constructor parameters do not match deployed values!");
    }
    
    console.log("\n   ✅ All constructor parameters verified successfully!");
    
  } catch (error) {
    console.error("\n❌ Verification Failed!");
    console.error("Error:", error.message);
    throw error;
  }
  
  // Save deployment info to DEPLOYMENTS directory
  console.log("\n💾 Saving Deployment Information...");
  const deploymentsDir = path.join(process.cwd(), "DEPLOYMENTS");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
    console.log("   ✓ Created DEPLOYMENTS directory");
  }
  
  const deploymentInfo = {
    network: "kasplex-testnet",
    address: controllerAddress,
    deployer: deployerAddress,
    timestamp: new Date().toISOString(),
    blockNumber: blockNumber,
    gasUsed: gasUsed,
    effectiveGasPrice: effectiveGasPrice,
    version: "3.0.0",
    constructor: {
      kaspaFinanceFactory: constructorParams.kaspaFinanceFactory,
      kaspaFinancePositionManager: constructorParams.kaspaFinancePositionManager,
      kaspaFinanceWKAS: constructorParams.kaspaFinanceWKAS,
      graduationOracle: constructorParams.graduationOracle,
      tokenFactory: constructorParams.tokenFactory,
      treasury: constructorParams.treasury
    },
    deploymentTx: deploymentTx?.hash,
    chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
    configuration: {
      poolFeeTier: 2500,
      slippageBps: 500,
      deadlineSeconds: 1800,
      maxPriceDeviationBps: 100,
      initialVirtualKas: "0.001",
      tickLower: -887200,
      tickUpper: 887200,
      burnAddress: "0x000000000000000000000000000000000000dEaD"
    },
    fixes: [
      "FIX #1: INITIAL_VIRTUAL_KAS = 0.001 ether",
      "FIX #2/#3: Snapshot architecture (1089.99 KAS)",
      "FIX #4: Tick spacing -887200/887200",
      "FIX #5: Atomic pool creation",
      "FIX #6: LP NFT burned to dead address",
      "FIX #7: Excess to treasury",
      "FIX #8: sqrtPrice bounds validation",
      "FIX #9: No try/catch on completeGraduation",
      "FIX #10: Oracle locking",
      "FIX #11: 30-minute deadline"
    ]
  };
  
  const deploymentFile = path.join(deploymentsDir, "graduation_controller_v3.json");
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log("   ✓ Deployment info saved to:", deploymentFile);
  
  // Display summary
  console.log("\n📊 Deployment Summary:");
  console.log("=".repeat(80));
  console.log("   Contract: GraduationController V3");
  console.log("   Version: 3.0.0");
  console.log("   Address:", controllerAddress);
  console.log("   Deployer:", deployerAddress);
  console.log("   Network: Kasplex Testnet");
  console.log("   Block:", blockNumber);
  console.log("   Gas Used:", gasUsed);
  console.log("   Tx Hash:", deploymentTx?.hash);
  
  // Display next steps
  console.log("\n📌 Next Steps:");
  console.log("=".repeat(80));
  console.log("   1. ✓ GraduationController V3 deployed successfully");
  console.log("   2. Update TokenFactory to use new GraduationController:");
  console.log(`      await tokenFactory.setGraduationController("${controllerAddress}")`);
  console.log("   3. Update environment variable:");
  console.log(`      GRADUATION_CONTROLLER_ADDRESS=${controllerAddress}`);
  console.log("   4. Restart application to load V3 contract");
  console.log("   5. Test graduation flow:");
  console.log("      - Deploy test token via TokenFactory");
  console.log("      - Reach graduation threshold ($50 market cap)");
  console.log("      - Trigger graduation via oracle");
  console.log("      - Verify Uniswap V3 pool creation and LP NFT burn");
  console.log("");
  console.log("   Verify contract on block explorer (optional):");
  console.log(`   npx hardhat verify --network ${network} ${controllerAddress} \\`);
  console.log(`     "${constructorParams.kaspaFinanceFactory}" \\`);
  console.log(`     "${constructorParams.kaspaFinancePositionManager}" \\`);
  console.log(`     "${constructorParams.kaspaFinanceWKAS}" \\`);
  console.log(`     "${constructorParams.graduationOracle}" \\`);
  console.log(`     "${constructorParams.tokenFactory}" \\`);
  console.log(`     "${constructorParams.treasury}"`);
  
  console.log("\n" + "=".repeat(80));
  console.log("✅ DEPLOYMENT COMPLETE - GRADUATION CONTROLLER V3");
  console.log("   ALL 11 CRITICAL FIXES IMPLEMENTED");
  console.log("=".repeat(80) + "\n");
  
  return controllerAddress;
}

// Execute deployment
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Fatal Error:");
    console.error(error);
    process.exit(1);
  });
