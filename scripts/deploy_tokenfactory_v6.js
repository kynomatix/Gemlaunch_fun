import { ethers } from "hardhat";

async function main() {
    console.log("Deploying TokenFactory V6 with GraduationController V4 baked in...\n");
    
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Balance:", ethers.formatEther(balance), "KAS\n");
    
    // V4 GraduationController address (BAKED IN - NO UPDATES NEEDED)
    const GRADUATION_CONTROLLER_V4 = "0x01Be48DeA4a1a8e4D625E6C2f253D05ebdb59031";
    
    // Treasury and wallet addresses
    const TREASURY = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const AIRDROP_TREASURY = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const PLATFORM_DEV = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
    const ADMIN = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const BUYBACK = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const KASPA_SUPPORT = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    const COMMUNITY = "0xe281e4776FB5De20817D0bbC72B0C4b955565619";
    
    console.log("Deployment Parameters:");
    console.log("  GraduationController V4:", GRADUATION_CONTROLLER_V4);
    console.log("  Treasury:", TREASURY);
    console.log("  Oracle:", ORACLE);
    console.log();
    
    console.log("Deploying TokenFactory V6...");
    const TokenFactory = await ethers.getContractFactory("TokenFactory");
    const factory = await TokenFactory.deploy(
        GRADUATION_CONTROLLER_V4,
        TREASURY,
        AIRDROP_TREASURY,
        PLATFORM_DEV,
        ORACLE,
        ADMIN,
        BUYBACK,
        KASPA_SUPPORT,
        COMMUNITY
    );
    
    await factory.waitForDeployment();
    const factoryAddress = await factory.getAddress();
    
    console.log("\n✅ TokenFactory V6 deployed:", factoryAddress);
    
    // Verify deployment
    console.log("\nVerifying deployment...");
    const deployedGC = await factory.graduationController();
    const vestingDeployer = await factory.vestingDeployer();
    
    console.log("  GraduationController:", deployedGC);
    console.log("  VestingDeployer:", vestingDeployer);
    console.log("  Owner:", await factory.owner());
    
    if (deployedGC.toLowerCase() === GRADUATION_CONTROLLER_V4.toLowerCase()) {
        console.log("\n✅ SUCCESS - V4 is BAKED IN");
        console.log("   No on-chain updates needed ever");
        console.log("   All tokens will use V4 automatically");
    } else {
        console.log("\n❌ VERIFICATION FAILED");
        process.exit(1);
    }
    
    console.log("\n📝 Next Steps:");
    console.log("1. Update TOKEN_FACTORY_ADDRESS in services/web3_service.py to:", factoryAddress);
    console.log("2. Update VESTING_DEPLOYER_ADDRESS in services/web3_service.py to:", vestingDeployer);
    console.log("3. Create test token - it will automatically use V4");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
