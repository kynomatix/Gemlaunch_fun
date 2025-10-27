import hre from "hardhat";

async function main() {
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    const EXPECTED_WKAS = "0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94";
    
    const gcAbi = ["function kaspaFinanceWKAS() view returns (address)"];
    const gc = await hre.ethers.getContractAt(gcAbi, GC_V9);
    
    const actualWKAS = await gc.kaspaFinanceWKAS();
    
    console.log("WKAS Verification:");
    console.log("==================");
    console.log(`Expected: ${EXPECTED_WKAS}`);
    console.log(`Actual:   ${actualWKAS}`);
    console.log(actualWKAS.toLowerCase() === EXPECTED_WKAS.toLowerCase() ? "✅ MATCH" : "❌ MISMATCH!");
    
    // Test if we can deposit to WKAS
    const wkasAbi = [
        "function deposit() payable",
        "function balanceOf(address) view returns (uint256)",
        "function approve(address,uint256) returns (bool)"
    ];
    
    try {
        const wkas = await hre.ethers.getContractAt(wkasAbi, actualWKAS);
        const gcBalance = await wkas.balanceOf(GC_V9);
        console.log(`\nGC's WKAS balance: ${hre.ethers.formatEther(gcBalance)} WKAS`);
        
        // Check if WKAS contract is functional
        const code = await hre.ethers.provider.getCode(actualWKAS);
        console.log(`WKAS contract exists: ${code !== '0x' ? '✅ Yes' : '❌ No'}`);
    } catch (e) {
        console.error("Error checking WKAS:", e.message);
    }
}

main().catch(console.error);
