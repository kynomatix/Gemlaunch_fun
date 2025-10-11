import hre from "hardhat";

/**
 * Helper script to display secondary wallet address and private key
 * Used for recovering the derived secondary wallet that controls admin/oracle/airdropTreasury roles
 * 
 * Usage:
 *   node scripts/get_secondary_wallet.js
 */

async function main() {
  console.log("\n🔐 Secondary Wallet Recovery Tool\n");
  console.log("=" .repeat(80));
  
  const deployerPrivateKey = process.env.DEPLOYER_PRIVATE_KEY;
  
  if (!deployerPrivateKey) {
    throw new Error("DEPLOYER_PRIVATE_KEY not found in environment");
  }
  
  // Derive secondary wallet using the same method as deploy_factory.js
  const derivedKey = hre.ethers.keccak256(
    hre.ethers.concat([
      hre.ethers.toUtf8Bytes("GEMLAUNCH_SECONDARY_WALLET"),
      hre.ethers.getBytes(deployerPrivateKey)
    ])
  );
  
  const secondaryWallet = new hre.ethers.Wallet(derivedKey);
  
  console.log("\n📋 Secondary Wallet Information:");
  console.log("   Address:", secondaryWallet.address);
  console.log("   Private Key:", derivedKey);
  
  console.log("\n🎯 Controls These Roles:");
  console.log("   - admin");
  console.log("   - graduationOracle");
  console.log("   - airdropTreasury");
  
  console.log("\n💡 How to Use:");
  console.log("   1. Save the private key securely");
  console.log("   2. Import into MetaMask or other wallet");
  console.log("   3. Use for admin/oracle operations");
  
  console.log("\n⚠️  Security Note:");
  console.log("   This wallet is deterministically derived from DEPLOYER_PRIVATE_KEY");
  console.log("   If you lose the deployer key, you also lose access to this wallet");
  console.log("   For production, use separate hardware wallets");
  
  console.log("\n" + "=" .repeat(80) + "\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
