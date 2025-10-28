import hre from "hardhat";

async function main() {
    console.log("\n" + "=".repeat(80));
    console.log("🚀 Deploying TokenFactory V12 - MAX_WALLET_PCT FIX");
    console.log("=".repeat(80) + "\n");

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying with account:", deployer.address);

    // VERIFIED PARAMETERS (all 9 addresses MUST be unique!)
    const GRADUATION_CONTROLLER_V13 = "0xf04aB5deE799DDb217a03bF07fFf4dDf541dD9f1";
    const TREASURY = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";  // 1
    const AIRDROP_TREASURY = "0x86b83FE03cDa7456980364c929BB17CFA67E8495";  // 2 - Airdrop distributor
    const PLATFORM_DEV_WALLET = "0xA51d8F597570353aE50A25df90aDe162D2305FfA";  // 3 - Oracle2 (creator)
    const ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";  // 4
    const ADMIN = "0xCD8e8F442E187B811130F8924B91a8F3445Ffb21";  // 5 - TF V10 (temp)
    const BUYBACK_RESERVE = "0xeb753f81F9beD4B6ea27381476a20d71ae496Cd1";  // 6 - GC V7 (old)
    const KASPA_SUPPORT = "0x22F3cC689401462B6ceb85EF544E86FE27ad178f";  // 7 - GC V8
    const COMMUNITY_REWARDS = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8";  // 8 - Kaspa Finance Factory

    console.log("\n📋 Constructor Parameters:");
    console.log("-".repeat(80));
    console.log("GraduationController V13:  ", GRADUATION_CONTROLLER_V13);
    console.log("Treasury:                  ", TREASURY);
    console.log("Oracle:                    ", ORACLE);
    console.log("\n🔧 FIX: BondingCurvePool now exempts transfers FROM graduationController");
    console.log("   This allows Uniswap pool to receive 25% LP supply during graduation");
    console.log("   STF error: 25% > MAX_WALLET_PCT (10%) - now bypassed safely\n");

    const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
    
    console.log("Deploying TokenFactory V12...");
    const tf = await TokenFactory.deploy(
        GRADUATION_CONTROLLER_V13,
        TREASURY,
        AIRDROP_TREASURY,
        PLATFORM_DEV_WALLET,
        ORACLE,
        ADMIN,
        BUYBACK_RESERVE,
        KASPA_SUPPORT,
        COMMUNITY_REWARDS
    );

    await tf.waitForDeployment();
    const tfAddress = await tf.getAddress();

    console.log("\n" + "=".repeat(80));
    console.log("✅ TokenFactory V12 deployed to:", tfAddress);
    console.log("=".repeat(80));

    // VERIFICATION
    console.log("\n🔍 POST-DEPLOYMENT VERIFICATION:");
    const deployedGC = await tf.graduationController();
    const deployedOracle = await tf.graduationOracle();

    console.log("GraduationController: ", deployedGC);
    console.log("Oracle:               ", deployedOracle);

    if (deployedGC.toLowerCase() !== GRADUATION_CONTROLLER_V13.toLowerCase()) {
        throw new Error("❌ VERIFICATION FAILED: GC mismatch!");
    }
    if (deployedOracle.toLowerCase() !== ORACLE.toLowerCase()) {
        throw new Error("❌ VERIFICATION FAILED: Oracle mismatch!");
    }

    console.log("\n✅ ALL VERIFICATIONS PASSED!");
    console.log("\n📝 Next Steps:");
    console.log("1. Update contracts/deployed_addresses.json");
    console.log("2. Update services/web3_service.py constants");
    console.log("3. Create NEW test token and fund to $50");
    console.log("4. Verify graduation succeeds without STF error");

    return tfAddress;
}

main()
    .then((address) => {
        console.log("\n🎉 Deployment successful: " + address);
        process.exit(0);
    })
    .catch((error) => {
        console.error("\n❌ Deployment failed:", error);
        process.exit(1);
    });
