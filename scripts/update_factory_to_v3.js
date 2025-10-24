import hre from "hardhat";

/**
 * Update TokenFactory to use GraduationController V3
 * 
 * CRITICAL FIX: TokenFactory still points to V2 controller (0x147e3ecbe189bb301175001706ff1f44df33b3ab)
 * This script updates it to V3 (0x2b68832db449f82bf70907a033bf279c73209b59)
 * which has all 11 critical fixes.
 */

async function main() {
    const [deployer] = await hre.ethers.getSigners();
    
    console.log("=" .repeat(80));
    console.log("UPDATING TOKENFACTORY TO GRADUATIONCONTROLLER V3");
    console.log("=".repeat(80));
    console.log("\n🔧 Deployer:", deployer.address);
    
    const balance = await hre.ethers.provider.getBalance(deployer.address);
    console.log("💰 Balance:", hre.ethers.formatEther(balance), "KAS");
    
    const FACTORY_ADDRESS = "0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc";
    const V3_CONTROLLER_ADDRESS = "0x2b68832db449f82bf70907a033bf279c73209b59";
    
    console.log("\n📋 Configuration:");
    console.log("   TokenFactory:", FACTORY_ADDRESS);
    console.log("   GraduationController V3:", V3_CONTROLLER_ADDRESS);
    
    // Load TokenFactory contract
    const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
    const factory = TokenFactory.attach(FACTORY_ADDRESS);
    
    // Check current graduation controller
    console.log("\n🔍 Checking current configuration...");
    const currentGC = await factory.graduationController();
    console.log("   Current graduationController:", currentGC);
    
    if (currentGC.toLowerCase() === V3_CONTROLLER_ADDRESS.toLowerCase()) {
        console.log("\n✅ Already up to date! No action needed.");
        return;
    }
    
    // Check owner
    const owner = await factory.owner();
    console.log("\n🔐 Contract owner:", owner);
    console.log("   Deployer:", deployer.address);
    
    if (owner.toLowerCase() !== deployer.address.toLowerCase()) {
        throw new Error(`❌ Not authorized! Owner is ${owner}, you are ${deployer.address}`);
    }
    
    console.log("   ✅ Authorized to update");
    
    // Update graduation controller
    console.log("\n📝 Calling setGraduationController...");
    const tx = await factory.setGraduationController(V3_CONTROLLER_ADDRESS);
    console.log("   Transaction hash:", tx.hash);
    console.log("   Waiting for confirmation...");
    
    const receipt = await tx.wait();
    console.log("   ✅ Confirmed in block:", receipt.blockNumber);
    console.log("   Gas used:", receipt.gasUsed.toString());
    
    // Verify update
    console.log("\n✅ Verifying update...");
    const updatedGC = await factory.graduationController();
    console.log("   New graduationController:", updatedGC);
    
    if (updatedGC.toLowerCase() === V3_CONTROLLER_ADDRESS.toLowerCase()) {
        console.log("\n🎉 SUCCESS! TokenFactory now uses GraduationController V3");
        console.log("   All new tokens will have the 11 critical fixes:");
        console.log("   ✅ Correct liquidity calculation (1089.99 KAS not 89.991)");
        console.log("   ✅ Valid tick spacing (multiples of 50)");
        console.log("   ✅ LP NFT burned to 0xdEaD (permanent lock)");
        console.log("   ✅ 30-minute deadline (not 30 seconds)");
        console.log("   ✅ Snapshot-based reserve calculation");
        console.log("   ✅ And 6 more critical fixes");
    } else {
        throw new Error(`❌ Update failed! Still points to ${updatedGC}`);
    }
    
    console.log("\n" + "=".repeat(80));
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("\n❌ Error:", error.message);
        process.exit(1);
    });
