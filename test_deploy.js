import { ethers } from 'ethers';
import fs from 'fs';

// Simple test to deploy AirdropDistributor
async function main() {
  console.log("Testing deployment...\n");
  
  const rpcUrl = "https://rpc.kasplextest.xyz";
  const privateKey = process.env.DEPLOYER_PRIVATE_KEY;
  
  if (!privateKey) {
    throw new Error("DEPLOYER_PRIVATE_KEY not set");
  }
  
  console.log("1. Connecting to RPC:", rpcUrl);
  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const wallet = new ethers.Wallet(privateKey, provider);
  
  console.log("   Deployer:", wallet.address);
  
  const balance = await provider.getBalance(wallet.address);
  console.log("   Balance:", ethers.formatEther(balance), "KAS\n");
  
  console.log("2. Loading contract ABI and bytecode...");
  const artifact = JSON.parse(fs.readFileSync('./artifacts/contracts/AirdropDistributor.sol/AirdropDistributor.json', 'utf8'));
  
  console.log("   Bytecode length:", artifact.bytecode.length);
  console.log("   ABI methods:", artifact.abi.length, "\n");
  
  console.log("3. Creating contract factory...");
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);
  
  console.log("4. Getting gas parameters...");
  const feeData = await provider.getFeeData();
  console.log("   Gas price:", ethers.formatUnits(feeData.gasPrice, "gwei"), "gwei");
  console.log("   Max fee:", feeData.maxFeePerGas ? ethers.formatUnits(feeData.maxFeePerGas, "gwei") + " gwei" : "N/A");
  
  console.log("\n5. Deploying contract...");
  const deployTx = await factory.getDeployTransaction();
  
  console.log("   Estimated gas:", await provider.estimateGas(deployTx));
  
  console.log("\n6. Sending transaction with 30s timeout...");
  try {
    const tx = await wallet.sendTransaction({
      data: artifact.bytecode,
      gasLimit: 3000000,
      gasPrice: feeData.gasPrice
    });
    
    console.log("   ✅ TX sent:", tx.hash);
    console.log("   Nonce:", tx.nonce);
    console.log("   Waiting for receipt...");
    
    const receipt = await tx.wait(1, 30000); // 30 second timeout
    
    console.log("\n✅ DEPLOYED!");
    console.log("   Contract:", receipt.contractAddress);
    console.log("   Block:", receipt.blockNumber);
    console.log("   Gas used:", receipt.gasUsed.toString());
    
  } catch (error) {
    console.log("\n❌ Error:", error.message);
    if (error.code === 'TIMEOUT') {
      console.log("   Transaction timed out but may still be pending");
    }
  }
}

main().catch(console.error);
