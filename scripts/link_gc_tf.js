import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("=== Linking GC V6 ← → TF V8 ===\n");
  
  // Load deployed addresses
  const registry = JSON.parse(fs.readFileSync('contracts/deployed_addresses.json', 'utf8'));
  
  const GC_ADDR = registry.contracts.GraduationController.address;
  const TF_ADDR = registry.contracts.TokenFactory.address;
  
  console.log(`GraduationController V6: ${GC_ADDR}`);
  console.log(`TokenFactory V8:         ${TF_ADDR}`);
  
  // Load GC contract
  const GC = await hre.ethers.getContractFactory("GraduationControllerV3");
  const gc = GC.attach(GC_ADDR);
  
  console.log("\nCalling GC.setTokenFactory()...");
  
  const tx = await gc.setTokenFactory(TF_ADDR);
  await tx.wait();
  
  console.log(`✅ GC.setTokenFactory() confirmed`);
  console.log(`   TX: ${tx.hash}`);
  
  // Verify the link
  console.log("\n=== Verifying Contract Links ===\n");
  
  const gcToTf = await gc.tokenFactory();
  console.log(`GC.tokenFactory(): ${gcToTf}`);
  console.log(`Expected:          ${TF_ADDR}`);
  console.log(`Match: ${gcToTf.toLowerCase() === TF_ADDR.toLowerCase() ? '✅' : '❌'}`);
  
  // Load TF and verify reverse link
  const TF = await hre.ethers.getContractFactory("TokenFactory");
  const tf = TF.attach(TF_ADDR);
  
  const tfToGc = await tf.graduationController();
  console.log(`\nTF.graduationController(): ${tfToGc}`);
  console.log(`Expected:                  ${GC_ADDR}`);
  console.log(`Match: ${tfToGc.toLowerCase() === GC_ADDR.toLowerCase() ? '✅' : '❌'}`);
  
  if (gcToTf.toLowerCase() === TF_ADDR.toLowerCase() && 
      tfToGc.toLowerCase() === GC_ADDR.toLowerCase()) {
    console.log("\n✅ ALL LINKS VERIFIED - Contracts properly connected!");
  } else {
    console.log("\n❌ LINK MISMATCH - Something is wrong!");
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
