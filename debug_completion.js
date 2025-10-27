import hre from "hardhat";

async function main() {
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    const CRNCH_POOL = "0x6aba77de0bd17062287778e8502d822b473d8d1c";
    const ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
    
    const [deployer] = await hre.ethers.getSigners();
    console.log("Calling from:", deployer.address);
    
    // Connect as Oracle wallet
    const gcAbi = [
        "function completeGraduation(address) external",
        "function graduationSnapshots(address) view returns (uint256,uint256,uint160,uint24,uint32,bool,bool,address,address)"
    ];
    
    const gc = await hre.ethers.getContractAt(gcAbi, GC_V9);
    
    // Check snapshot
    const snapshot = await gc.graduationSnapshots(CRNCH_POOL);
    console.log("\nSnapshot:", {
        kasLiquidity: hre.ethers.formatEther(snapshot[0]),
        tokenLiquidity: hre.ethers.formatUnits(snapshot[1], 18),
        targetSqrtPrice: snapshot[2].toString(),
        initiatedAt: snapshot[4],
        poolInitialized: snapshot[5],
        lpMinted: snapshot[6]
    });
    
    console.log("\n🚀 Attempting completeGraduation...");
    
    try {
        // Try with static call first for better error
        await gc.completeGraduation.staticCall(CRNCH_POOL);
        console.log("✅ Static call succeeded");
    } catch (error) {
        console.log("\n❌ Static call failed:");
        console.log("Error message:", error.message);
        
        // Try to decode revert data
        if (error.data) {
            console.log("Revert data:", error.data);
            
            // Try to decode as string
            try {
                const decoded = hre.ethers.toUtf8String(error.data);
                console.log("Decoded:", decoded);
            } catch (e) {
                console.log("Could not decode as string");
            }
        }
        
        // Check if it's a require message
        if (error.message.includes("execution reverted")) {
            const match = error.message.match(/execution reverted: (.+)/);
            if (match) {
                console.log("Revert reason:", match[1]);
            }
        }
    }
}

main().catch(console.error);
