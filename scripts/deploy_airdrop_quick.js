import hre from "hardhat";

async function main() {
  console.log("Deploying AirdropDistributor...");
  
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deployer:", deployer.address);
  
  const AirdropDistributor = await hre.ethers.getContractFactory("AirdropDistributor");
  
  // Get gas parameters
  const feeData = await hre.ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice ? feeData.gasPrice * 120n / 100n : undefined;
  console.log(`Gas price: ${gasPrice ? hre.ethers.formatUnits(gasPrice, "gwei") : "auto"} gwei`);
  
  // Send deployment transaction
  const distributor = await AirdropDistributor.deploy({
    gasPrice: gasPrice,
    gasLimit: 3000000
  });
  
  const txHash = distributor.deploymentTransaction()?.hash;
  console.log("\n✅ Transaction sent!");
  console.log(`TX Hash: ${txHash}`);
  console.log(`Track at: https://explorer.testnet.kasplextest.xyz/tx/${txHash}`);
  
  // Try to get the contract address from the transaction
  const deployTx = distributor.deploymentTransaction();
  console.log("\nWaiting for confirmation (timeout after 2 minutes)...");
  
  try {
    const receipt = await Promise.race([
      distributor.waitForDeployment(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 120000))
    ]);
    
    const address = await distributor.getAddress();
    console.log(`\n✅ Contract deployed: ${address}`);
    console.log(`View at: https://explorer.testnet.kasplextest.xyz/address/${address}`);
    
    return address;
  } catch (error) {
    if (error.message === 'Timeout') {
      console.log("\n⏰ Deployment is taking longer than expected.");
      console.log("The transaction was sent and should complete eventually.");
      console.log(`Check status at: https://explorer.testnet.kasplextest.xyz/tx/${txHash}`);
      console.log("\nTo find the contract address once mined, check the transaction receipt.");
    } else {
      throw error;
    }
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Error:");
    console.error(error.message);
    process.exit(1);
  });
