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
function validateConstraints(params) {
  const errors = [];
  
  // Check for zero addresses
  Object.entries(params).forEach(([key, value]) => {
    if (value === hre.ethers.ZeroAddress) {
      errors.push(`${key} cannot be zero address`);
    }
  });
  
  // Check duplicate constraints from contract
  if (params.treasury === params.admin) {
    errors.push("treasury cannot be admin (contract constraint)");
  }
  
  if (params.treasury === params.graduationOracle) {
    errors.push("treasury cannot be graduationOracle (contract constraint)");
  }
  
  if (params.airdropTreasury === params.platformDevelopmentWallet) {
    errors.push("airdropTreasury cannot be platformDevelopmentWallet (contract constraint)");
  }
  
  return errors;
}

async function main() {
  console.log("\n🚀 Deploying TokenFactory to Kasplex Testnet...\n");
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
  
  console.log("\n💼 Primary Wallet (Deployer):");
  console.log("   Address:", deployerAddress);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS");
  console.log("   Roles:", config.wallets?.primary?.roles?.join(", ") || "treasury, platformDev, reserves");
  
  if (balance === 0n) {
    throw new Error("❌ Deployer wallet has no KAS! Fund it first.");
  }
  
  // Get secondary wallet (for admin/oracle/airdropTreasury)
  console.log("\n🔐 Secondary Wallet (Admin/Oracle):");
  const secondaryWallet = await getSecondaryWallet(deployer);
  const secondaryAddress = await secondaryWallet.getAddress();
  const secondaryBalance = await hre.ethers.provider.getBalance(secondaryAddress);
  
  console.log("   Address:", secondaryAddress);
  console.log("   Balance:", hre.ethers.formatEther(secondaryBalance), "KAS");
  console.log("   Roles:", config.wallets?.secondary?.roles?.join(", ") || "admin, oracle, airdropTreasury");
  console.log("   Control: ✓ CONTROLLED (derived from deployer)");
  
  // Verify addresses are different
  if (deployerAddress === secondaryAddress) {
    throw new Error("❌ Secondary wallet must differ from deployer!");
  }
  
  // Deploy VestingDeployer first (required by TokenFactory)
  console.log("\n🏗️  Deploying VestingDeployer Contract...");
  console.log("=" .repeat(80));
  
  // We'll pass factory address after factory is deployed (chicken-egg problem)
  // So we deploy with deployer address first, then update via constructor param
  const VestingDeployer = await hre.ethers.getContractFactory("VestingDeployer");
  
  // Note: We need to pass future factory address. Deploy with placeholder then redeploy.
  // Actually, we need to calculate CREATE address deterministically
  // Factory will be deployed by deployer at nonce N+1
  
  // Get current nonce to calculate future factory address
  const currentNonce = await hre.ethers.provider.getTransactionCount(deployerAddress);
  const futureFactoryAddress = hre.ethers.getCreateAddress({
    from: deployerAddress,
    nonce: currentNonce + 1  // VestingDeployer is currentNonce, Factory is currentNonce+1
  });
  
  console.log("   Calculated future TokenFactory address:", futureFactoryAddress);
  console.log("   (Factory will be deployed at nonce:", currentNonce + 1, ")");
  
  const vestingDeployer = await VestingDeployer.deploy(futureFactoryAddress);
  
  console.log("   ✓ Transaction sent!");
  console.log("   Tx hash:", vestingDeployer.deploymentTransaction()?.hash);
  console.log("   Waiting for confirmation...");
  
  await vestingDeployer.waitForDeployment();
  const vestingDeployerAddress = await vestingDeployer.getAddress();
  
  console.log("\n✅ VestingDeployer Deployed Successfully!");
  console.log("   Contract address:", vestingDeployerAddress);
  console.log("   Factory address (configured):", futureFactoryAddress);
  
  // Verify deployment
  const vestingCode = await hre.ethers.provider.getCode(vestingDeployerAddress);
  if (vestingCode === "0x") {
    throw new Error("VestingDeployer deployment failed - no code at address");
  }
  console.log("   ✓ Contract code verified at address");
  
  // Build constructor parameters
  const constructorParams = {
    graduationController: deployerAddress,
    treasury: deployerAddress,
    airdropTreasury: secondaryAddress,
    platformDevelopmentWallet: deployerAddress,
    graduationOracle: secondaryAddress,
    admin: secondaryAddress,
    buybackReserveWallet: deployerAddress,
    kaspaNetworkSupportWallet: deployerAddress,
    communityRewardsWallet: deployerAddress,
    vestingDeployer: vestingDeployerAddress
  };
  
  // Validate constraints
  console.log("\n✅ Validating Contract Constraints...");
  const validationErrors = validateConstraints(constructorParams);
  
  if (validationErrors.length > 0) {
    console.error("\n❌ Validation failed:");
    validationErrors.forEach(error => console.error("   -", error));
    throw new Error("Constructor parameter validation failed");
  }
  
  console.log("   ✓ treasury != admin");
  console.log("   ✓ treasury != graduationOracle");
  console.log("   ✓ airdropTreasury != platformDevelopmentWallet");
  console.log("   ✓ All addresses non-zero");
  console.log("   ✓ All addresses CONTROLLED");
  
  // Display constructor parameters
  console.log("\n📝 Constructor Parameters:");
  console.log("=" .repeat(80));
  console.table({
    "graduationController (temp)": { address: constructorParams.graduationController, wallet: "Primary" },
    "treasury": { address: constructorParams.treasury, wallet: "Primary" },
    "airdropTreasury": { address: constructorParams.airdropTreasury, wallet: "Secondary" },
    "platformDevelopmentWallet": { address: constructorParams.platformDevelopmentWallet, wallet: "Primary" },
    "graduationOracle": { address: constructorParams.graduationOracle, wallet: "Secondary" },
    "admin": { address: constructorParams.admin, wallet: "Secondary" },
    "buybackReserveWallet": { address: constructorParams.buybackReserveWallet, wallet: "Primary" },
    "kaspaNetworkSupportWallet": { address: constructorParams.kaspaNetworkSupportWallet, wallet: "Primary" },
    "communityRewardsWallet": { address: constructorParams.communityRewardsWallet, wallet: "Primary" },
    "vestingDeployer": { address: constructorParams.vestingDeployer, wallet: "Contract" }
  });
  
  // Estimate gas
  console.log("\n⛽ Estimating Deployment Gas...");
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const deploymentData = TokenFactory.interface.encodeDeploy([
    constructorParams.graduationController,
    constructorParams.treasury,
    constructorParams.airdropTreasury,
    constructorParams.platformDevelopmentWallet,
    constructorParams.graduationOracle,
    constructorParams.admin,
    constructorParams.buybackReserveWallet,
    constructorParams.kaspaNetworkSupportWallet,
    constructorParams.communityRewardsWallet,
    constructorParams.vestingDeployer
  ]);

  const estimatedGas = await hre.ethers.provider.estimateGas({
    from: deployerAddress,
    data: TokenFactory.bytecode + deploymentData.slice(2)
  });

  const feeData = await hre.ethers.provider.getFeeData();
  console.log("   Estimated gas:", estimatedGas.toString());
  console.log("   Gas price:", feeData.gasPrice?.toString() || "auto");
  
  // Deploy TokenFactory
  console.log("\n🏗️  Deploying TokenFactory Contract...");
  console.log("=" .repeat(80));
  
  try {
    const tokenFactory = await TokenFactory.deploy(
      constructorParams.graduationController,
      constructorParams.treasury,
      constructorParams.airdropTreasury,
      constructorParams.platformDevelopmentWallet,
      constructorParams.graduationOracle,
      constructorParams.admin,
      constructorParams.buybackReserveWallet,
      constructorParams.kaspaNetworkSupportWallet,
      constructorParams.communityRewardsWallet,
      constructorParams.vestingDeployer
    );

    console.log("   ✓ Transaction sent!");
    console.log("   Tx hash:", tokenFactory.deploymentTransaction()?.hash);
    console.log("   Waiting for confirmation...");

    await tokenFactory.waitForDeployment();
    const factoryAddress = await tokenFactory.getAddress();
    const blockNumber = await hre.ethers.provider.getBlockNumber();

    console.log("\n🎉 TokenFactory Deployed Successfully!");
    console.log("=" .repeat(80));
    console.log("   Contract address:", factoryAddress);
    console.log("   Block number:", blockNumber);
    console.log("   Network:", network);
    console.log("   Chain ID:", (await hre.ethers.provider.getNetwork()).chainId);

    // Verify deployment by calling view functions
    console.log("\n🔍 Verifying Deployment...");
    const owner = await tokenFactory.owner();
    const treasuryAddr = await tokenFactory.treasury();
    const adminAddr = await tokenFactory.admin();
    const cooldown = await tokenFactory.deploymentCooldown();
    
    console.log("   ✓ Owner:", owner);
    console.log("   ✓ Treasury:", treasuryAddr);
    console.log("   ✓ Admin:", adminAddr);
    console.log("   ✓ Deployment cooldown:", cooldown.toString(), "seconds");
    
    // Verify addresses match
    if (owner !== deployerAddress) {
      console.warn("   ⚠️  Warning: Owner doesn't match deployer");
    }
    if (treasuryAddr !== constructorParams.treasury) {
      console.warn("   ⚠️  Warning: Treasury doesn't match expected");
    }

    // Verify factory address matches calculated address
    if (factoryAddress !== futureFactoryAddress) {
      console.warn("   ⚠️  Warning: Factory address doesn't match calculated address");
      console.warn("   Expected:", futureFactoryAddress);
      console.warn("   Got:", factoryAddress);
    } else {
      console.log("   ✓ Factory address matches calculated address");
    }
    
    // Save deployment info
    const deploymentInfo = {
      network: network,
      chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
      tokenFactory: factoryAddress,
      vestingDeployer: vestingDeployerAddress,
      deployer: deployerAddress,
      wallets: {
        primary: {
          address: deployerAddress,
          roles: ["owner", "treasury", "platformDevelopmentWallet", "buybackReserve", "kaspaSupport", "communityRewards", "graduationController (temp)"]
        },
        secondary: {
          address: secondaryAddress,
          roles: ["admin", "graduationOracle", "airdropTreasury"],
          controlled: true,
          derivedFromDeployer: !process.env.SECONDARY_PRIVATE_KEY
        }
      },
      constructorParams: constructorParams,
      deploymentTx: tokenFactory.deploymentTransaction()?.hash,
      vestingDeployerTx: vestingDeployer.deploymentTransaction()?.hash,
      timestamp: new Date().toISOString(),
      blockNumber: blockNumber
    };

    // Save to deployments directory
    const deploymentsDir = path.join(process.cwd(), "deployments");
    if (!fs.existsSync(deploymentsDir)) {
      fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    const deploymentFile = path.join(deploymentsDir, `${network}_factory.json`);
    fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
    console.log("\n💾 Deployment Info Saved:", deploymentFile);

    // Display wallet control summary
    console.log("\n🔑 Wallet Control Summary:");
    console.log("=" .repeat(80));
    console.log("   PRIMARY WALLET (Deployer):", deployerAddress);
    console.log("   - Controls: Treasury, Platform Dev, Reserves, Owner");
    console.log("   - Private Key: DEPLOYER_PRIVATE_KEY (in .env)");
    console.log("");
    console.log("   SECONDARY WALLET:", secondaryAddress);
    console.log("   - Controls: Admin, Oracle, Airdrop Treasury");
    if (process.env.SECONDARY_PRIVATE_KEY) {
      console.log("   - Private Key: SECONDARY_PRIVATE_KEY (in .env)");
    } else {
      console.log("   - Private Key: Derived from DEPLOYER_PRIVATE_KEY (deterministic)");
      console.log("   - ⚠️  Can be recovered using same derivation method");
    }

    // Display next steps
    console.log("\n📌 Next Steps:");
    console.log("=" .repeat(80));
    console.log("   1. ✓ VestingDeployer deployed at:", vestingDeployerAddress);
    console.log("   2. ✓ TokenFactory deployed with CONTROLLED addresses only");
    console.log("   3. Deploy GraduationController contract");
    console.log("   4. Update graduationController address:");
    console.log("      await tokenFactory.setGraduationController(graduationControllerAddress)");
    console.log("   5. Test token creation");
    console.log("");
    console.log("   Verify VestingDeployer (optional):");
    console.log(`   npx hardhat verify --network ${network} ${vestingDeployerAddress} "${factoryAddress}"`);
    console.log("");
    console.log("   Verify TokenFactory (optional):");
    console.log(`   npx hardhat verify --network ${network} ${factoryAddress} \\`);
    console.log(`     "${constructorParams.graduationController}" \\`);
    console.log(`     "${constructorParams.treasury}" \\`);
    console.log(`     "${constructorParams.airdropTreasury}" \\`);
    console.log(`     "${constructorParams.platformDevelopmentWallet}" \\`);
    console.log(`     "${constructorParams.graduationOracle}" \\`);
    console.log(`     "${constructorParams.admin}" \\`);
    console.log(`     "${constructorParams.buybackReserveWallet}" \\`);
    console.log(`     "${constructorParams.kaspaNetworkSupportWallet}" \\`);
    console.log(`     "${constructorParams.communityRewardsWallet}" \\`);
    console.log(`     "${constructorParams.vestingDeployer}"`);

    console.log("\n" + "=" .repeat(80));
    console.log("✅ DEPLOYMENT COMPLETE - ALL ADDRESSES CONTROLLED");
    console.log("=" .repeat(80) + "\n");

    return factoryAddress;

  } catch (error) {
    console.error("\n❌ Deployment Failed!");
    console.error("=" .repeat(80));
    console.error("Error:", error.message);
    
    if (error.message.includes("Treasury cannot be admin") ||
        error.message.includes("Treasury cannot be oracle") ||
        error.message.includes("Duplicate wallets")) {
      console.error("\n⚠️  Contract validation failed:");
      console.error("   - Ensure treasury != admin");
      console.error("   - Ensure treasury != graduationOracle");
      console.error("   - Ensure airdropTreasury != platformDevelopmentWallet");
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
