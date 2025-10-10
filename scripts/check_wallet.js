import hre from "hardhat";

async function main() {
  console.log("\n🔍 Checking Testnet Connection...\n");
  
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  const balance = await hre.ethers.provider.getBalance(deployerAddress);
  
  console.log("✅ Network:", hre.network.name);
  console.log("✅ Chain ID:", (await hre.ethers.provider.getNetwork()).chainId);
  console.log("✅ RPC URL:", hre.network.config.url);
  console.log("\n💼 Deployer Wallet:");
  console.log("   Address:", deployerAddress);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS");
  
  if (balance === 0n) {
    console.log("\n⚠️  WARNING: Wallet has no KAS. Get testnet KAS from faucet!");
  } else {
    console.log("\n✅ Wallet funded and ready for deployment!");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
