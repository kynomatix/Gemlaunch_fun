import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    console.log("\n" + "=".repeat(80));
    console.log("🔍 COMPREHENSIVE ADDRESS VERIFICATION");
    console.log("=".repeat(80) + "\n");

    // 1. Check TokenFactory V11
    const tfAddress = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1";
    const tf = await ethers.getContractAt("TokenFactory", tfAddress);
    const tfGC = await tf.graduationController();
    
    console.log("TokenFactory V11:           ", tfAddress);
    console.log("  graduationController():   ", tfGC);
    console.log("");

    // 2. Check GraduationController V9
    const gcV9Address = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    const gcV9 = await ethers.getContractAt("GraduationControllerV3", gcV9Address);
    const gcV9Factory = await gcV9.tokenFactory();
    
    console.log("GraduationController V9:    ", gcV9Address);
    console.log("  tokenFactory():           ", gcV9Factory);
    console.log("");

    // 3. Check GraduationController V8
    const gcV8Address = "0x22F3cC689401462B6ceb85EF544E86FE27ad178f";
    const gcV8 = await ethers.getContractAt("GraduationControllerV3", gcV8Address);
    const gcV8Factory = await gcV8.tokenFactory();
    
    console.log("GraduationController V8:    ", gcV8Address);
    console.log("  tokenFactory():           ", gcV8Factory);
    console.log("");

    // 4. Check $CYBR Pool
    const cybrAddress = "0x7da3452a3c51053eb87b3d0cf97b5469fb837530";
    const cybr = await ethers.getContractAt("BondingCurvePool", cybrAddress);
    const cybrFactory = await cybr.factory();
    
    console.log("$CYBR Pool:                 ", cybrAddress);
    console.log("  factory():                ", cybrFactory);
    console.log("");

    // 5. Verification
    console.log("=".repeat(80));
    console.log("VERIFICATION:");
    console.log("=".repeat(80));
    
    const cybrMatchesTF11 = cybrFactory.toLowerCase() === tfAddress.toLowerCase();
    const tfGCMatchesV9 = tfGC.toLowerCase() === gcV9Address.toLowerCase();
    const gcV9FactoryMatchesTF11 = gcV9Factory.toLowerCase() === tfAddress.toLowerCase();
    
    console.log("✓ $CYBR was deployed by TF V11:           ", cybrMatchesTF11);
    console.log("✓ TF V11 points to GC V9:                 ", tfGCMatchesV9);
    console.log("✓ GC V9's factory is TF V11:              ", gcV9FactoryMatchesTF11);
    console.log("");
    
    if (cybrMatchesTF11 && tfGCMatchesV9 && gcV9FactoryMatchesTF11) {
        console.log("🟢 ALL CHECKS PASS - Configuration is CORRECT!");
        console.log("");
        console.log("🔴 BUT initiation is failing - checking isDeployedPool()...");
        
        const isDeployed = await tf.isDeployedPool(cybrAddress);
        console.log("TF V11.isDeployedPool($CYBR): ", isDeployed);
        
        if (!isDeployed) {
            console.log("");
            console.log("🚨 ROOT CAUSE FOUND:");
            console.log("   TokenFactory V11 doesn't recognize $CYBR in its registry!");
            console.log("   This means TF V11 was redeployed AFTER $CYBR was created.");
        }
    } else {
        console.log("🔴 CONFIGURATION MISMATCH DETECTED!");
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
