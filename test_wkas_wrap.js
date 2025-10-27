import hre from "hardhat";

async function main() {
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    const WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94";
    const ORACLE = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E";
    
    const [deployer] = await hre.ethers.getSigners();
    
    // Check GC's KAS balance
    const gcKasBalance = await hre.ethers.provider.getBalance(GC_V9);
    console.log(`GC KAS Balance: ${hre.ethers.formatEther(gcKasBalance)} KAS`);
    
    // Try to call WKAS.deposit as if we were GC
    const wkasAbi = ["function deposit() payable", "function balanceOf(address) view returns (uint256)"];
    const wkas = await hre.ethers.getContractAt(wkasAbi, WKAS);
    
    console.log("\n🧪 Testing WKAS.deposit() operation...");
    
    try {
        // Simulate wrapping 920.7 KAS
        const kasAmount = hre.ethers.parseEther("920.7");
        
        // Static call to test if it would work
        await wkas.deposit.staticCall({ value: kasAmount, from: GC_V9 });
        console.log("✅ WKAS.deposit() would succeed");
        
        // Check if GC can receive WKAS
        const wkasBalance = await wkas.balanceOf(GC_V9);
        console.log(`Current WKAS balance: ${hre.ethers.formatEther(wkasBalance)} WKAS`);
        
    } catch (error) {
        console.log("❌ WKAS.deposit() would fail:");
        console.log("Error:", error.message);
        if (error.data) {
            console.log("Error data:", error.data);
        }
    }
}

main().catch(console.error);
