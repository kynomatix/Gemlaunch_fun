import hre from "hardhat";

async function main() {
    const CRNCH_POOL = "0x6aba77de0bd17062287778e8502d822b473d8d1c";
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    
    const poolAbi = ["function balanceOf(address) view returns (uint256)", "function totalSupply() view returns (uint256)"];
    const pool = await hre.ethers.getContractAt(poolAbi, CRNCH_POOL);
    
    const gcBalance = await pool.balanceOf(GC_V9);
    const totalSupply = await pool.totalSupply();
    const expectedLP = totalSupply * 25n / 100n;
    
    console.log("CRNCH Token Balances:");
    console.log("=====================");
    console.log(`Total Supply:     ${hre.ethers.formatUnits(totalSupply, 18)} CRNCH`);
    console.log(`Expected LP (25%): ${hre.ethers.formatUnits(expectedLP, 18)} CRNCH`);
    console.log(`GC V9 Balance:    ${hre.ethers.formatUnits(gcBalance, 18)} CRNCH`);
    console.log("");
    
    if (gcBalance >= expectedLP) {
        console.log("✅ GC has sufficient tokens");
    } else {
        console.log("❌ GC missing tokens!");
        console.log(`   Shortfall: ${hre.ethers.formatUnits(expectedLP - gcBalance, 18)} CRNCH`);
    }
    
    // Check KAS balance
    const kasBalance = await hre.ethers.provider.getBalance(GC_V9);
    console.log(`\nGC V9 KAS Balance: ${hre.ethers.formatEther(kasBalance)} KAS`);
}

main().catch(console.error);
