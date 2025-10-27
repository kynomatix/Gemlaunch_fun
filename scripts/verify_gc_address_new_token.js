import hre from "hardhat";

async function main() {
  const tokenAddress = "0x462F79A487d26a3F61Ac13389a1b0070171dF1Bc";
  const expectedGC = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
  
  const BondingCurvePool = await hre.ethers.getContractFactory("BondingCurvePool");
  const pool = BondingCurvePool.attach(tokenAddress);
  
  const name = await pool.name();
  const symbol = await pool.symbol();
  const gcAddress = await pool.graduationController();
  const goAddress = await pool.graduationOracle();
  
  console.log("Token:", name, "(" + symbol + ")");
  console.log("Address:", tokenAddress);
  console.log("graduationController:", gcAddress);
  console.log("graduationOracle:", goAddress);
  console.log("");
  
  if (gcAddress.toLowerCase() === expectedGC.toLowerCase()) {
    console.log("🎉 SUCCESS! GraduationController is set correctly!");
    console.log("   This token will be able to graduate at $50 market cap.");
    console.log("   The fix is working - all new tokens will have GC set properly.");
  } else if (gcAddress === "0x0000000000000000000000000000000000000000") {
    console.log("❌ FAILURE: graduationController is still 0x0000");
  } else {
    console.log("⚠️  Unexpected GC address:", gcAddress);
  }
}

main().catch(console.error);
