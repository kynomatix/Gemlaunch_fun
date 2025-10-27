import hre from "hardhat";

async function main() {
  console.log("🚀 Creating test token to verify GraduationController initialization...\n");
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Creating from wallet:", deployer.address);
  
  // Get balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Wallet balance:", hre.ethers.formatEther(balance), "KAS\n");
  
  // Load TokenFactory
  const tokenFactoryAddress = "0xDe2a7Ef9A8e29EDF2f6A16a3Ca6fe512E88c9211";
  const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
  const factory = TokenFactory.attach(tokenFactoryAddress);
  
  console.log("Using TokenFactory:", tokenFactoryAddress);
  
  // Verify factory config
  const factoryGC = await factory.graduationController();
  const factoryGO = await factory.graduationOracle();
  console.log("Factory GraduationController:", factoryGC);
  console.log("Factory GraduationOracle:", factoryGO);
  console.log("");
  
  // Token parameters (13 parameters - beneficiaries are automatic now)
  const tokenParams = {
    name: "GC Test Token",
    symbol: "GCTEST",
    totalSupply: hre.ethers.parseEther("1000000000"), // 1B tokens
    description: "Test token to verify GraduationController initialization fix",
    imageUrl: "",
    twitterUrl: "",
    telegramUrl: "",
    websiteUrl: "",
    antiBotEnabled: false,
    reservedPercentage: 0,
    airdropAllocation: 0,
    marketingAllocation: 0,
    teamAllocation: 0
  };
  
  console.log("📋 Creating token:", tokenParams.symbol, "-", tokenParams.name);
  console.log("   Total Supply:", hre.ethers.formatEther(tokenParams.totalSupply));
  console.log("   Anti-Bot:", tokenParams.antiBotEnabled);
  console.log("");
  
  // Create token (13 parameters + initial KAS deposit)
  console.log("📤 Sending createToken transaction...");
  const tx = await factory.createToken(
    tokenParams.name,
    tokenParams.symbol,
    tokenParams.totalSupply,
    tokenParams.description,
    tokenParams.imageUrl,
    tokenParams.twitterUrl,
    tokenParams.telegramUrl,
    tokenParams.websiteUrl,
    tokenParams.antiBotEnabled,
    tokenParams.reservedPercentage,
    tokenParams.airdropAllocation,
    tokenParams.marketingAllocation,
    tokenParams.teamAllocation,
    { value: hre.ethers.parseEther("0.001") } // Initial KAS deposit
  );
  
  console.log("Transaction hash:", tx.hash);
  console.log("⏳ Waiting for confirmation...");
  
  const receipt = await tx.wait();
  console.log("✅ Transaction confirmed in block:", receipt.blockNumber);
  console.log("");
  
  // Find TokenCreated event
  const tokenCreatedEvent = receipt.logs
    .map(log => {
      try {
        return factory.interface.parseLog(log);
      } catch {
        return null;
      }
    })
    .find(event => event && event.name === "TokenCreated");
  
  if (!tokenCreatedEvent) {
    console.log("❌ TokenCreated event not found!");
    return;
  }
  
  const poolAddress = tokenCreatedEvent.args.tokenAddress;
  console.log("🎉 Token created successfully!");
  console.log("   Pool Address:", poolAddress);
  console.log("");
  
  // Verify GraduationController is set
  console.log("🔍 Verifying GraduationController address...");
  const BondingCurvePool = await hre.ethers.getContractFactory("BondingCurvePool");
  const pool = BondingCurvePool.attach(poolAddress);
  
  const gcAddress = await pool.graduationController();
  const goAddress = await pool.graduationOracle();
  
  console.log("   graduationController:", gcAddress);
  console.log("   graduationOracle:", goAddress);
  console.log("");
  
  // Expected values
  const expectedGC = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
  const expectedGO = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
  
  // Verify
  let success = true;
  
  if (gcAddress.toLowerCase() !== expectedGC.toLowerCase()) {
    if (gcAddress === hre.ethers.ZeroAddress) {
      console.log("❌ CRITICAL: graduationController is 0x0000 (not set)!");
      console.log("   The fix did NOT work!");
    } else {
      console.log("⚠️  WARNING: graduationController set but unexpected address");
      console.log("   Expected:", expectedGC);
      console.log("   Got:", gcAddress);
    }
    success = false;
  } else {
    console.log("✅ graduationController is set correctly!");
  }
  
  if (goAddress.toLowerCase() !== expectedGO.toLowerCase()) {
    console.log("⚠️  WARNING: graduationOracle unexpected address");
    console.log("   Expected:", expectedGO);
    console.log("   Got:", goAddress);
    success = false;
  } else {
    console.log("✅ graduationOracle is set correctly!");
  }
  
  console.log("");
  if (success) {
    console.log("🎉 SUCCESS! The fix is working!");
    console.log("   All new tokens will have graduationController set correctly");
    console.log("   Graduation will work when tokens reach $50 market cap");
  } else {
    console.log("❌ FAILURE! Something is still wrong with the deployment");
  }
  
  console.log("");
  console.log("📝 Token Details:");
  console.log("   Symbol:", tokenParams.symbol);
  console.log("   Address:", poolAddress);
  console.log("   Explorer:", `https://explorer.testnet.kasplextest.xyz/address/${poolAddress}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
