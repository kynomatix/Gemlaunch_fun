import hre from "hardhat";
const { ethers } = hre;

async function main() {
    console.log("Deploying GraduationController V4 to Kasplex Testnet...");
    
    const [deployer] = await ethers.getSigners();
    console.log("Deployer:", deployer.address);
    
    // Get deployer balance
    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Deployer balance:", ethers.formatEther(balance), "KAS");
    
    // Kaspa Finance addresses on Kasplex Testnet (properly checksummed)
    const KASPA_FINANCE_POSITION_MANAGER = "0x6B55ee3477d25fdA21c345798ce8e33A6f0C7A7B";
    const KASPA_FINANCE_WKAS = "0x8940Fe0d0e4e1bbD1B076E1Fd2c56a4133978fd4";
    const KASPA_FINANCE_FACTORY = "0x9d0bFe8fB0b36C8fc7b6DC3AD00Eee87ba07a04A";
    
    // Deployment parameters (properly checksummed)
    const TREASURY_ADDRESS = "0xe281e4776FB5De20817D0bbC72B0C4b955565619"; // Deployer as treasury
    const GRADUATION_ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"; // Oracle wallet
    const TOKEN_FACTORY = "0xDe2a7Ef9A8e29EDF2f6A16a3Ca6fe512E88c9211"; // TokenFactory V5
    
    console.log("\nDeployment Parameters:");
    console.log("  Position Manager:", KASPA_FINANCE_POSITION_MANAGER);
    console.log("  WKAS:", KASPA_FINANCE_WKAS);
    console.log("  Factory:", KASPA_FINANCE_FACTORY);
    console.log("  Treasury:", TREASURY_ADDRESS);
    console.log("  Oracle:", GRADUATION_ORACLE);
    console.log("  Token Factory:", TOKEN_FACTORY);
    
    // Deploy GraduationController V4
    const GraduationController = await ethers.getContractFactory("GraduationControllerV3");
    
    console.log("\nDeploying GraduationController V4...");
    const graduationController = await GraduationController.deploy(
        KASPA_FINANCE_POSITION_MANAGER,
        KASPA_FINANCE_WKAS,
        KASPA_FINANCE_FACTORY,
        TREASURY_ADDRESS,
        GRADUATION_ORACLE,
        TOKEN_FACTORY
    );
    
    await graduationController.waitForDeployment();
    const gcAddress = await graduationController.getAddress();
    
    console.log("\n✅ GraduationController V4 deployed to:", gcAddress);
    
    // Verify deployment
    console.log("\nVerifying deployment...");
    const owner = await graduationController.owner();
    const oracle = await graduationController.graduationOracle();
    const factory = await graduationController.tokenFactory();
    
    console.log("  Owner:", owner);
    console.log("  Oracle:", oracle);
    console.log("  Token Factory:", factory);
    
    console.log("\n🎉 Deployment complete!");
    console.log("\nNext steps:");
    console.log("1. Update GRADUATION_CONTROLLER_ADDRESS in config/blockchain.py to:", gcAddress);
    console.log("2. Update TokenFactory to point to new GC (if needed)");
    console.log("3. Test graduation with new token");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
