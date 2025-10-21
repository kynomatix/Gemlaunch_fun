import hre from "hardhat";

async function main() {
  console.log("Deploying TestMinimal (tiniest possible contract)...\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer:", deployer.address);

  const TestMinimal = await hre.ethers.getContractFactory("TestMinimal");
  console.log("Sending deployment...");
  
  const contract = await TestMinimal.deploy();
  const txHash = contract.deploymentTransaction()?.hash;
  
  console.log("TX:", txHash);
  console.log("Waiting...");
  
  await contract.waitForDeployment();
  console.log("✅ Deployed:", await contract.getAddress());
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌", error.message);
    process.exit(1);
  });
