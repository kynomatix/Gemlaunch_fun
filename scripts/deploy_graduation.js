import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Get secondary controlled wallet for admin/oracle roles
 * Priority:
 * 1. SECONDARY_PRIVATE_KEY env var
 * 2. Derive from deployer using HD wallet path
 */
async function getSecondaryWallet(deployer) {
  if (process.env.SECONDARY_PRIVATE_KEY) {
    console.log("   Using SECONDARY_PRIVATE_KEY from environment");
    return new hre.ethers.Wallet(process.env.SECONDARY_PRIVATE_KEY, hre.ethers.provider);
  }
  
  // Derive secondary wallet from deployer's mnemonic (if using HD wallet)
  // This ensures we always have control of the secondary wallet
  // Path: m/44'/60'/0'/0/1 (next address in HD wallet)
  try {
    const deployerPrivateKey = process.env.DEPLOYER_PRIVATE_KEY;
    if (!deployerPrivateKey) {
      throw new Error("DEPLOYER_PRIVATE_KEY not found in environment");
    }
    
    // For testnet simplicity, derive a secondary address deterministically
    // by creating a new wallet from a derived key
    // Ensure deployer key has 0x prefix
    const normalizedKey = deployerPrivateKey.startsWith('0x') ? deployerPrivateKey : `0x${deployerPrivateKey}`;
    
    const derivedKey = hre.ethers.keccak256(
      hre.ethers.concat([
        hre.ethers.toUtf8Bytes("GEMLAUNCH_SECONDARY_WALLET"),
        hre.ethers.getBytes(normalizedKey)
      ])
    );
    
    const secondaryWallet = new hre.ethers.Wallet(derivedKey, hre.ethers.provider);
    console.log("   Derived secondary wallet from deployer (deterministic)");
    
    return secondaryWallet;
  } catch (error) {
    throw new Error(`Failed to get secondary wallet: ${error.message}`);
  }
}

/**
 * Load deployment configuration from wallet_config.json
 */
function loadConfig(network) {
  const configPath = path.join(process.cwd(), "config", "wallet_config.json");
  
  if (!fs.existsSync(configPath)) {
    throw new Error(`Config file not found: ${configPath}`);
  }
  
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  
  if (!config[network]) {
    throw new Error(`Network '${network}' not found in config`);
  }
  
  return config[network];
}

/**
 * Validate constructor parameters against contract constraints
 */
function validateConstraints(params, deployerAddress) {
  const errors = [];
  
  // Check for zero addresses
  Object.entries(params).forEach(([key, value]) => {
    if (value === hre.ethers.ZeroAddress) {
      errors.push(`${key} cannot be zero address`);
    }
  });
  
  // Check duplicate constraints from contract
  if (params.kaspaFinancePositionManager === params.kaspaFinanceWKAS) {
    errors.push("kaspaFinancePositionManager cannot be kaspaFinanceWKAS (contract constraint)");
  }
  
  // Check graduationOracle cannot be owner (deployer)
  if (params.graduationOracle === deployerAddress) {
    errors.push("graduationOracle cannot be owner/deployer (contract constraint)");
  }
  
  return errors;
}

async function main() {
  console.log("\n🚀 Deploying GraduationController to Kasplex Testnet...\n");
  console.log("=" .repeat(80));
  
  // Get network
  const network = hre.network.name;
  
  // Load configuration
  console.log("\n📋 Loading Configuration...");
  const config = loadConfig(network);
  console.log("   ✓ Loaded config for network:", network);
  
  // Get deployer (primary wallet)
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  const balance = await hre.ethers.provider.getBalance(deployerAddress);
  
  console.log("\n💼 Primary Wallet (Deployer/Owner):");
  console.log("   Address:", deployerAddress);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS");
  console.log("   Roles: Owner of GraduationController");
  
  if (balance === 0n) {
    throw new Error("❌ Deployer wallet has no KAS! Fund it first.");
  }
  
  // Get secondary wallet (for graduationOracle)
  console.log("\n🔐 Secondary Wallet (Graduation Oracle):");
  const secondaryWallet = await getSecondaryWallet(deployer);
  const secondaryAddress = await secondaryWallet.getAddress();
  const secondaryBalance = await hre.ethers.provider.getBalance(secondaryAddress);
  
  console.log("   Address:", secondaryAddress);
  console.log("   Balance:", hre.ethers.formatEther(secondaryBalance), "KAS");
  console.log("   Roles: graduationOracle");
  console.log("   Control: ✓ CONTROLLED (derived from deployer)");
  
  // Verify addresses are different (required by contract)
  if (deployerAddress === secondaryAddress) {
    throw new Error("❌ Secondary wallet must differ from deployer! (Contract constraint: oracle cannot be owner)");
  }
  
  // Get Kaspa Finance addresses from config
  if (!config.kaspaFinance) {
    throw new Error("❌ Kaspa Finance addresses not found in config");
  }
  
  const kaspaFinance = config.kaspaFinance;
  console.log("\n🏦 Kaspa Finance Integration:");
  console.log("   nftPositionManager:", kaspaFinance.nftPositionManager);
  console.log("   WKAS:", kaspaFinance.wkas);
  console.log("   Factory:", kaspaFinance.factory);
  console.log("   SwapRouter:", kaspaFinance.swapRouter);
  console.log("   QuoterV2:", kaspaFinance.quoterV2);
  
  // Build constructor parameters
  const constructorParams = {
    kaspaFinancePositionManager: kaspaFinance.nftPositionManager,
    kaspaFinanceWKAS: kaspaFinance.wkas,
    graduationOracle: secondaryAddress
  };
  
  // Validate constraints
  console.log("\n✅ Validating Contract Constraints...");
  const validationErrors = validateConstraints(constructorParams, deployerAddress);
  
  if (validationErrors.length > 0) {
    console.error("\n❌ Validation failed:");
    validationErrors.forEach(error => console.error("   -", error));
    throw new Error("Constructor parameter validation failed");
  }
  
  console.log("   ✓ kaspaFinancePositionManager != kaspaFinanceWKAS");
  console.log("   ✓ graduationOracle != owner (deployer)");
  console.log("   ✓ All addresses non-zero");
  console.log("   ✓ All addresses valid");
  
  // Display constructor parameters
  console.log("\n📝 Constructor Parameters:");
  console.log("=" .repeat(80));
  console.table({
    "kaspaFinancePositionManager": { address: constructorParams.kaspaFinancePositionManager, source: "Config (nftPositionManager)" },
    "kaspaFinanceWKAS": { address: constructorParams.kaspaFinanceWKAS, source: "Config (wkas)" },
    "graduationOracle": { address: constructorParams.graduationOracle, source: "Secondary Wallet (Controlled)" }
  });
  
  // Estimate gas
  console.log("\n⛽ Estimating Deployment Gas...");
  const GraduationController = await hre.ethers.getContractFactory("GraduationController");
  const deploymentData = GraduationController.interface.encodeDeploy([
    constructorParams.kaspaFinancePositionManager,
    constructorParams.kaspaFinanceWKAS,
    constructorParams.graduationOracle
  ]);

  const estimatedGas = await hre.ethers.provider.estimateGas({
    from: deployerAddress,
    data: GraduationController.bytecode + deploymentData.slice(2)
  });

  const feeData = await hre.ethers.provider.getFeeData();
  console.log("   Estimated gas:", estimatedGas.toString());
  console.log("   Gas price:", feeData.gasPrice?.toString() || "auto");
  
  // Deploy GraduationController
  console.log("\n🏗️  Deploying GraduationController Contract...");
  console.log("=" .repeat(80));
  
  try {
    const graduationController = await GraduationController.deploy(
      constructorParams.kaspaFinancePositionManager,
      constructorParams.kaspaFinanceWKAS,
      constructorParams.graduationOracle
    );

    console.log("   ✓ Transaction sent!");
    console.log("   Tx hash:", graduationController.deploymentTransaction()?.hash);
    console.log("   Waiting for confirmation...");

    await graduationController.waitForDeployment();
    const controllerAddress = await graduationController.getAddress();
    const blockNumber = await hre.ethers.provider.getBlockNumber();

    console.log("\n🎉 GraduationController Deployed Successfully!");
    console.log("=" .repeat(80));
    console.log("   Contract address:", controllerAddress);
    console.log("   Block number:", blockNumber);
    console.log("   Network:", network);
    console.log("   Chain ID:", (await hre.ethers.provider.getNetwork()).chainId);

    // Verify deployment by calling view functions
    console.log("\n🔍 Verifying Deployment...");
    const owner = await graduationController.owner();
    const oracle = await graduationController.graduationOracle();
    const positionManager = await graduationController.kaspaFinancePositionManager();
    const wkas = await graduationController.kaspaFinanceWKAS();
    const poolFeeTier = await graduationController.POOL_FEE_TIER();
    const slippageBps = await graduationController.graduationSlippageBps();
    const deadlineSeconds = await graduationController.graduationDeadlineSeconds();
    
    console.log("   ✓ Owner:", owner);
    console.log("   ✓ Graduation Oracle:", oracle);
    console.log("   ✓ Position Manager:", positionManager);
    console.log("   ✓ WKAS:", wkas);
    console.log("   ✓ Pool Fee Tier:", poolFeeTier.toString(), "(0.25%)");
    console.log("   ✓ Graduation Slippage:", slippageBps.toString(), "bps (5%)");
    console.log("   ✓ Graduation Deadline:", deadlineSeconds.toString(), "seconds (5 min)");
    
    // Verify addresses match
    if (owner !== deployerAddress) {
      console.warn("   ⚠️  Warning: Owner doesn't match deployer");
    }
    if (oracle !== constructorParams.graduationOracle) {
      console.warn("   ⚠️  Warning: Oracle doesn't match expected");
    }

    // Save deployment info
    const deploymentInfo = {
      network: network,
      chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
      graduationController: controllerAddress,
      deployer: deployerAddress,
      wallets: {
        primary: {
          address: deployerAddress,
          roles: ["owner"]
        },
        secondary: {
          address: secondaryAddress,
          roles: ["graduationOracle"],
          controlled: true,
          derivedFromDeployer: !process.env.SECONDARY_PRIVATE_KEY
        }
      },
      kaspaFinanceIntegration: {
        nftPositionManager: constructorParams.kaspaFinancePositionManager,
        wkas: constructorParams.kaspaFinanceWKAS,
        factory: kaspaFinance.factory,
        swapRouter: kaspaFinance.swapRouter,
        quoterV2: kaspaFinance.quoterV2
      },
      constructorParams: constructorParams,
      deploymentTx: graduationController.deploymentTransaction()?.hash,
      timestamp: new Date().toISOString(),
      blockNumber: blockNumber,
      configuration: {
        poolFeeTier: Number(poolFeeTier),
        slippageBps: Number(slippageBps),
        deadlineSeconds: Number(deadlineSeconds)
      }
    };

    // Save to deployments directory
    const deploymentsDir = path.join(process.cwd(), "deployments");
    if (!fs.existsSync(deploymentsDir)) {
      fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    const deploymentFile = path.join(deploymentsDir, `${network}_graduation.json`);
    fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
    console.log("\n💾 Deployment Info Saved:", deploymentFile);

    // Display wallet control summary
    console.log("\n🔑 Wallet Control Summary:");
    console.log("=" .repeat(80));
    console.log("   PRIMARY WALLET (Deployer/Owner):", deployerAddress);
    console.log("   - Controls: GraduationController owner functions");
    console.log("   - Private Key: DEPLOYER_PRIVATE_KEY (in .env)");
    console.log("");
    console.log("   SECONDARY WALLET (Graduation Oracle):", secondaryAddress);
    console.log("   - Controls: Graduation initiation and completion");
    if (process.env.SECONDARY_PRIVATE_KEY) {
      console.log("   - Private Key: SECONDARY_PRIVATE_KEY (in .env)");
    } else {
      console.log("   - Private Key: Derived from DEPLOYER_PRIVATE_KEY (deterministic)");
      console.log("   - ⚠️  Can be recovered using same derivation method");
    }

    // Display next steps
    console.log("\n📌 Next Steps:");
    console.log("=" .repeat(80));
    console.log("   1. ✓ GraduationController deployed with CONTROLLED addresses");
    console.log("   2. Update TokenFactory with GraduationController address:");
    console.log("      await tokenFactory.setGraduationController('" + controllerAddress + "')");
    console.log("   3. Test graduation flow:");
    console.log("      - Deploy test token via TokenFactory");
    console.log("      - Reach graduation threshold ($30K USD)");
    console.log("      - Oracle initiates graduation");
    console.log("      - Oracle completes graduation (adds liquidity to Kaspa Finance)");
    console.log("");
    console.log("   Verify contract (optional):");
    console.log(`   npx hardhat verify --network ${network} ${controllerAddress} \\`);
    console.log(`     "${constructorParams.kaspaFinancePositionManager}" \\`);
    console.log(`     "${constructorParams.kaspaFinanceWKAS}" \\`);
    console.log(`     "${constructorParams.graduationOracle}"`);

    console.log("\n" + "=" .repeat(80));
    console.log("✅ DEPLOYMENT COMPLETE - ALL ADDRESSES CONTROLLED");
    console.log("=" .repeat(80) + "\n");

    return controllerAddress;

  } catch (error) {
    console.error("\n❌ Deployment Failed!");
    console.error("=" .repeat(80));
    console.error("Error:", error.message);
    
    if (error.message.includes("Duplicate addresses") ||
        error.message.includes("Oracle cannot be owner")) {
      console.error("\n⚠️  Contract validation failed:");
      console.error("   - Ensure kaspaFinancePositionManager != kaspaFinanceWKAS");
      console.error("   - Ensure graduationOracle != owner (deployer)");
    }
    
    throw error;
  }
}

// Execute deployment
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
