import hre from "hardhat";

async function main() {
  console.log("Testing if we can send ANY transaction...\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("From:", deployer.address);
  
  // Try to send a tiny amount to ourselves (should be instant)
  console.log("Sending 0.001 KAS to self...");
  
  const tx = await deployer.sendTransaction({
    to: deployer.address,
    value: hre.ethers.parseEther("0.001")
  });
  
  console.log("✅ TX SENT:", tx.hash);
  console.log("Nonce:", tx.nonce);
  console.log("Waiting...");
  
  const receipt = await tx.wait(1, 20000); // 20s timeout
  console.log("✅ CONFIRMED in block", receipt.blockNumber);
}

main()
  .then(() => {
    console.log("\n✅ Simple transactions work!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("\n❌ Even simple transactions fail:", error.message);
    process.exit(1);
  });
