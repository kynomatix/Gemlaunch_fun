import hre from "hardhat";

async function main() {
  console.log("🔍 Verifying GraduationController address on RRGT token...\n");
  
  // RRGT token address (from user's creation)
  const tokenAddress = "0xe050923ad37519fbc51aa85fd5d296ee14ed5f6e";
  
  // Expected GraduationController address
  const expectedGCAddress = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
  
  console.log("Token Address:", tokenAddress);
  console.log("Expected GC Address:", expectedGCAddress);
  console.log("");
  
  // Load BondingCurvePool ABI
  const BondingCurvePool = await hre.ethers.getContractFactory("BondingCurvePool");
  const pool = BondingCurvePool.attach(tokenAddress);
  
  // Query graduationController address
  try {
    const gcAddress = await pool.graduationController();
    const goAddress = await pool.graduationOracle();
    
    console.log("📊 On-Chain Values:");
    console.log("  graduationController:", gcAddress);
    console.log("  graduationOracle:", goAddress);
    console.log("");
    
    // Verify
    if (gcAddress.toLowerCase() === expectedGCAddress.toLowerCase()) {
      console.log("✅ SUCCESS: graduationController is set correctly!");
      console.log("   This token will be able to graduate when it reaches $50 market cap.");
    } else if (gcAddress === "0x0000000000000000000000000000000000000000") {
      console.log("❌ FAILURE: graduationController is 0x0000 (not set)");
      console.log("   This would have blocked graduation.");
    } else {
      console.log("⚠️  WARNING: graduationController is set but to unexpected address");
      console.log("   Expected:", expectedGCAddress);
      console.log("   Got:", gcAddress);
    }
    
  } catch (error) {
    console.error("❌ Error querying contract:", error.message);
    process.exit(1);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
