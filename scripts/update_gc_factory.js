import pkg from 'hardhat';
const { ethers } = pkg;
import fs from 'fs';

/**
 * Update GraduationController V3 to authorize TokenFactory V5
 * 
 * This fixes the "Pool not deployed by authorized factory" error
 * by updating GC V3's tokenFactory reference from V4 to V5
 */

async function main() {
    console.log("🔧 Updating GraduationController V3 factory authorization...\n");
    
    // Addresses
    const GC_V3_ADDRESS = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
    const TOKEN_FACTORY_V5_ADDRESS = "0xDe2a7Ef9A8e29EDF2f6A16a3Ca6fe512E88c9211";
    
    // Get owner signer
    const [deployer] = await ethers.getSigners();
    console.log("Deployer/Owner:", deployer.address);
    
    // Load GraduationController V3
    const GraduationController = await ethers.getContractFactory("GraduationControllerV3");
    const gc = GraduationController.attach(GC_V3_ADDRESS);
    
    console.log("\n📋 Current Configuration:");
    const currentFactory = await gc.tokenFactory();
    const owner = await gc.owner();
    console.log("  GC V3 Address:", GC_V3_ADDRESS);
    console.log("  Owner:", owner);
    console.log("  Current Factory:", currentFactory);
    console.log("  New Factory (V5):", TOKEN_FACTORY_V5_ADDRESS);
    
    // Verify owner
    if (owner.toLowerCase() !== deployer.address.toLowerCase()) {
        throw new Error(`Deployer ${deployer.address} is not the owner ${owner}`);
    }
    
    // Check if update is needed
    if (currentFactory.toLowerCase() === TOKEN_FACTORY_V5_ADDRESS.toLowerCase()) {
        console.log("\n✅ Factory is already set to V5, no update needed");
        return;
    }
    
    console.log("\n🚀 Updating factory authorization...");
    
    // Call setTokenFactory
    const tx = await gc.setTokenFactory(TOKEN_FACTORY_V5_ADDRESS);
    console.log("  Transaction hash:", tx.hash);
    console.log("  Waiting for confirmation...");
    
    const receipt = await tx.wait();
    console.log("  ✅ Confirmed in block:", receipt.blockNumber);
    console.log("  Gas used:", receipt.gasUsed.toString());
    
    // Verify update
    const newFactory = await gc.tokenFactory();
    console.log("\n✅ Update verified:");
    console.log("  Old Factory:", currentFactory);
    console.log("  New Factory:", newFactory);
    
    if (newFactory.toLowerCase() === TOKEN_FACTORY_V5_ADDRESS.toLowerCase()) {
        console.log("\n🎉 SUCCESS! GraduationController V3 now authorizes TokenFactory V5");
        console.log("  ORING can now graduate successfully");
    } else {
        throw new Error("Factory update failed - address mismatch");
    }
    
    // Save deployment record
    const timestamp = Date.now();
    const deploymentRecord = {
        timestamp,
        date: new Date(timestamp).toISOString(),
        network: "kasplex_testnet",
        action: "update_gc_factory_authorization",
        graduationController: GC_V3_ADDRESS,
        oldFactory: currentFactory,
        newFactory: newFactory,
        txHash: tx.hash,
        blockNumber: receipt.blockNumber,
        gasUsed: receipt.gasUsed.toString()
    };
    
    const filename = `deployments/gc_factory_update_${timestamp}.json`;
    fs.writeFileSync(filename, JSON.stringify(deploymentRecord, null, 2));
    console.log("\n📝 Deployment record saved:", filename);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("\n❌ Error:", error);
        process.exit(1);
    });
