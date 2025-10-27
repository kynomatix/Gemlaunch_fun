import hre from "hardhat";

async function main() {
    console.log("\n" + "=".repeat(80));
    console.log("🚀 Deploying GraduationController V9");
    console.log("=".repeat(80) + "\n");

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying with account:", deployer.address);
    console.log("Account balance:", (await hre.ethers.provider.getBalance(deployer.address)).toString());

    // VERIFIED PARAMETERS FROM deployed_addresses.json
    const KASPA_FINANCE_FACTORY = "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8";
    const KASPA_FINANCE_POSITION_MANAGER = "0x4E25637cF39822364b877F81B18c5B6CF0eeF589";
    const KASPA_FINANCE_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94";
    const GRADUATION_ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
    const TOKEN_FACTORY_V11 = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1";  // FIX: Use V11!
    const TREASURY = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";

    console.log("\n📋 Constructor Parameters:");
    console.log("-".repeat(80));
    console.log("Kaspa Finance Factory:        ", KASPA_FINANCE_FACTORY);
    console.log("Kaspa Finance Position Mgr:   ", KASPA_FINANCE_POSITION_MANAGER);
    console.log("Kaspa Finance WKAS:           ", KASPA_FINANCE_WKAS);
    console.log("Graduation Oracle:            ", GRADUATION_ORACLE);
    console.log("Token Factory V11:            ", TOKEN_FACTORY_V11);
    console.log("Treasury:                     ", TREASURY);

    console.log("\n⚠️  CRITICAL VERIFICATION:");
    console.log("Oracle:   " + GRADUATION_ORACLE);
    console.log("Treasury: " + TREASURY);
    if (GRADUATION_ORACLE === TREASURY) {
        throw new Error("❌ FATAL: Oracle and Treasury are the same! Deployment ABORTED!");
    }
    console.log("✅ Oracle and Treasury are different - proceeding...\n");

    const GraduationController = await hre.ethers.getContractFactory("GraduationControllerV3");
    
    console.log("Deploying contract...");
    const gc = await GraduationController.deploy(
        KASPA_FINANCE_FACTORY,
        KASPA_FINANCE_POSITION_MANAGER,
        KASPA_FINANCE_WKAS,
        GRADUATION_ORACLE,
        TOKEN_FACTORY_V11,  // FIX: Using V11 instead of V10!
        TREASURY
    );

    await gc.waitForDeployment();
    const gcAddress = await gc.getAddress();

    console.log("\n" + "=".repeat(80));
    console.log("✅ GraduationController V9 deployed to:", gcAddress);
    console.log("=".repeat(80));

    // VERIFICATION: Read back the oracle address to confirm
    console.log("\n🔍 POST-DEPLOYMENT VERIFICATION:");
    const deployedOracle = await gc.graduationOracle();
    const deployedTreasury = await gc.treasury();
    const deployedFactory = await gc.tokenFactory();

    console.log("Oracle (from contract):       ", deployedOracle);
    console.log("Treasury (from contract):     ", deployedTreasury);
    console.log("TokenFactory (from contract): ", deployedFactory);

    if (deployedOracle.toLowerCase() !== GRADUATION_ORACLE.toLowerCase()) {
        throw new Error("❌ VERIFICATION FAILED: Oracle mismatch!");
    }
    if (deployedTreasury.toLowerCase() !== TREASURY.toLowerCase()) {
        throw new Error("❌ VERIFICATION FAILED: Treasury mismatch!");
    }
    if (deployedFactory.toLowerCase() !== TOKEN_FACTORY_V11.toLowerCase()) {
        throw new Error("❌ VERIFICATION FAILED: TokenFactory mismatch!");
    }

    console.log("\n✅ ALL VERIFICATIONS PASSED!");
    console.log("\n📝 Next Steps:");
    console.log("1. Update TokenFactory V11 to point to GC V9");
    console.log("2. Update contracts/deployed_addresses.json");
    console.log("3. Update services/web3_service.py constants");
    console.log("4. Test with $CYBR graduation");

    return gcAddress;
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
