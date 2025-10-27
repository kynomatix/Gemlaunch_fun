// Hardhat script to set GraduationController on test pool
// Run with: npx hardhat run scripts/set_gc_hardhat.js --network kasplex_testnet

const hre = require("hardhat");

const TOKEN_FACTORY = "0x408dcf382d38eCe30b2b25C86440f923CAa7B631";
const GRADUATION_CONTROLLER = "0x91e405C15F7aD99b2E669c7E745422c4DC8f5A89";
const FINALTEST_POOL = "0x7c9C7190fFc527ff9D550F435066C8c97AD0c020";

async function main() {
    console.log("=".repeat(60));
    console.log("Setting GraduationController on FINALTEST Pool");
    console.log("=".repeat(60));
    
    const [deployer] = await hre.ethers.getSigners();
    console.log(`Deployer: ${deployer.address}`);
    console.log(`TokenFactory: ${TOKEN_FACTORY}`);
    console.log(`GraduationController: ${GRADUATION_CONTROLLER}`);
    console.log(`FINALTEST Pool: ${FINALTEST_POOL}`);
    console.log();
    
    // Load contracts
    const TokenFactory = await hre.ethers.getContractFactory("TokenFactory");
    const tf = TokenFactory.attach(TOKEN_FACTORY);
    
    const BondingCurvePool = await hre.ethers.getContractFactory("BondingCurvePool");
    const pool = BondingCurvePool.attach(FINALTEST_POOL);
    
    // Verify ownership
    const tfOwner = await tf.owner();
    const poolOwner = await pool.owner();
    
    console.log("Current State:");
    console.log(`  TokenFactory owner: ${tfOwner}`);
    console.log(`  Pool owner: ${poolOwner}`);
    console.log(`  Pool GC: ${await pool.graduationController()}`);
    console.log();
    
    if (tfOwner.toLowerCase() !== deployer.address.toLowerCase()) {
        console.log("❌ ERROR: Deployer doesn't own TokenFactory");
        return;
    }
    
    if (poolOwner.toLowerCase() !== TOKEN_FACTORY.toLowerCase()) {
        console.log("❌ ERROR: TokenFactory doesn't own pool");
        return;
    }
    
    console.log("✅ Ownership verified");
    console.log();
    
    // Strategy: TokenFactory temporarily transfers pool to deployer, deployer sets GC, transfers back
    console.log("Step 1: TokenFactory transfers pool to deployer...");
    
    // Get the pool contract through TokenFactory
    const poolAsFactory = BondingCurvePool.attach(FINALTEST_POOL).connect(
        await hre.ethers.getImpersonatedSigner(TOKEN_FACTORY)
    );
    
    // Transfer ownership to deployer
    let tx = await poolAsFactory.transferOwnership(deployer.address);
    await tx.wait();
    console.log(`  ✅ Ownership transferred: ${tx.hash}`);
    
    // Step 2: Deployer sets GC
    console.log("\nStep 2: Setting GraduationController...");
    tx = await pool.setGraduationController(GRADUATION_CONTROLLER);
    await tx.wait();
    console.log(`  ✅ GC set: ${tx.hash}`);
    
    // Step 3: Transfer back to TokenFactory
    console.log("\nStep 3: Transferring pool back to TokenFactory...");
    tx = await pool.transferOwnership(TOKEN_FACTORY);
    await tx.wait();
    console.log(`  ✅ Ownership restored: ${tx.hash}`);
    
    // Verify final state
    console.log("\n" + "=".repeat(60));
    console.log("Final State:");
    console.log(`  Pool owner: ${await pool.owner()}`);
    console.log(`  Pool GC: ${await pool.graduationController()}`);
    console.log("=".repeat(60));
    
    const finalGC = await pool.graduationController();
    if (finalGC.toLowerCase() === GRADUATION_CONTROLLER.toLowerCase()) {
        console.log("\n✅ SUCCESS! GraduationController is set correctly!");
    } else {
        console.log("\n❌ FAILED! GC not set properly");
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
