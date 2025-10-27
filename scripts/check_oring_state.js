import hre from "hardhat";

async function main() {
  const poolAddress = "0x462F79A487d26a3F61Ac13389a1b0070171dF1Bc";
  const gcAddress = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
  
  const BondingCurvePool = await hre.ethers.getContractFactory("BondingCurvePool");
  const pool = BondingCurvePool.attach(poolAddress);
  
  const GC = await hre.ethers.getContractFactory("GraduationControllerV3");
  const gc = GC.attach(gcAddress);
  
  console.log("=== ORING ACTUAL On-Chain State ===\n");
  
  // Check pool's graduating flag
  const graduating = await pool.graduating();
  console.log("Pool.graduating():", graduating);
  
  // Check GC snapshot
  try {
    const snapshot = await gc.graduationSnapshots(poolAddress);
    console.log("\nGraduation Snapshot:");
    console.log("  poolContract:", snapshot.poolContract);
    console.log("  graduating:", snapshot.graduating);
    console.log("  kasLiquidity:", hre.ethers.formatEther(snapshot.kasLiquidity), "KAS");
    
    if (snapshot.poolContract === "0x0000000000000000000000000000000000000000") {
      console.log("\n❌ NO SNAPSHOT - Graduation was NOT initiated on-chain");
    } else {
      console.log("\n✅ Snapshot exists - Graduation IS initiated");
    }
  } catch (e) {
    console.log("\n❌ Error reading snapshot:", e.message);
  }
}

main().catch(console.error);
