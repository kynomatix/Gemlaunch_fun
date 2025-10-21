import hre from "hardhat";
import fs from "fs";

async function main() {
  console.log("Manual AirdropDistributor Deployment\n");

  const [deployer] = await hre.ethers.getSigners();
  console.log("1. Deployer:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("   Balance:", hre.ethers.formatEther(balance), "KAS\n");

  console.log("2. Loading contract artifact...");
  const artifact = JSON.parse(
    fs.readFileSync('./artifacts/contracts/AirdropDistributor.sol/AirdropDistributor.json', 'utf8')
  );
  console.log("   Bytecode size:", artifact.bytecode.length, "bytes\n");

  console.log("3. Getting gas parameters...");
  const feeData = await hre.ethers.provider.getFeeData();
  console.log("   Gas price:", feeData.gasPrice ? hre.ethers.formatUnits(feeData.gasPrice, "gwei") + " gwei" : "N/A");
  console.log("   Max fee:", feeData.maxFeePerGas ? hre.ethers.formatUnits(feeData.maxFeePerGas, "gwei") + " gwei" : "N/A\n");

  console.log("4. Building transaction...");
  const tx = {
    from: deployer.address,
    data: artifact.bytecode,
    gasLimit: 500000,
    ...(feeData.gasPrice && { gasPrice: feeData.gasPrice })
  };

  console.log("5. Estimating gas...");
  try {
    const gasEstimate = await hre.ethers.provider.estimateGas(tx);
    console.log("   Gas estimate:", gasEstimate.toString());
    tx.gasLimit = gasEstimate * 120n / 100n; // 20% buffer
    console.log("   Gas limit (with buffer):", tx.gasLimit.toString(), "\n");
  } catch (e) {
    console.log("   Could not estimate gas, using default:", tx.gasLimit.toString(), "\n");
  }

  console.log("6. Sending transaction...");
  console.log("   This should be instant...");
  
  const response = await deployer.sendTransaction(tx);
  
  console.log("\n✅ TRANSACTION SENT!");
  console.log("   TX Hash:", response.hash);
  console.log("   Nonce:", response.nonce);
  console.log("   Explorer: https://explorer.testnet.kasplextest.xyz/tx/" + response.hash);
  console.log("\n7. Waiting for confirmation (15s timeout)...");

  try {
    const receipt = await response.wait(1, 15000);
    console.log("\n✅ DEPLOYED!");
    console.log("   Contract:", receipt.contractAddress);
    console.log("   Block:", receipt.blockNumber);
    console.log("   Gas used:", receipt.gasUsed.toString());
    
    return receipt.contractAddress;
  } catch (e) {
    console.log("\n⏰ Timeout - check explorer for status");
    console.log("   Once mined, look for 'Contract Creation' in the tx details");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Error:", error.message);
    process.exit(1);
  });
