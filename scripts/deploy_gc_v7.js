import hre from "hardhat";
const { ethers } = hre;

async function main() {
    console.log("Deploying GraduationController V7 to Kasplex Testnet...");
    console.log("V7 FIX: Tokens transferred during pool.initiateGraduation() - no safeTransferFrom");
    
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
    const TOKEN_FACTORY = "0xB4D21bD000275F58A7180502Af5215fc4adE9984"; // TokenFactory V9
    
    console.log("\nDeployment Parameters:");
    console.log("  Position Manager:", KASPA_FINANCE_POSITION_MANAGER);
    console.log("  WKAS:", KASPA_FINANCE_WKAS);
    console.log("  Factory:", KASPA_FINANCE_FACTORY);
    console.log("  Treasury:", TREASURY_ADDRESS);
    console.log("  Oracle:", GRADUATION_ORACLE);
    console.log("  Token Factory:", TOKEN_FACTORY);
    
    // Deploy GraduationController V7 (compiled from GraduationControllerV3.sol)
    const GraduationController = await ethers.getContractFactory("GraduationControllerV3");
    
    console.log("\nDeploying GraduationController V7...");
    console.log("  Change: Tokens already transferred by pool, balance check instead of safeTransferFrom");
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
    
    console.log("\n✅ GraduationController V7 deployed to:", gcAddress);
    
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
    console.log("1. Deploy TokenFactory V10 pointing to this GC");
    console.log("2. Update contracts/deployed_addresses.json");
    console.log("3. Update services/web3_service.py constants");
    console.log("4. Test with new token");
    console.log("\nGC V7 Address:", gcAddress);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
