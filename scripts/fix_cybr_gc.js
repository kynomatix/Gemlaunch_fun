import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    console.log("\n" + "=".repeat(80));
    console.log("🔧 Fixing $CYBR GraduationController Reference");
    console.log("=".repeat(80) + "\n");

    const [deployer] = await hre.ethers.getSigners();
    console.log("Executing with account:", deployer.address);

    const cybrAddress = "0x7da3452a3c51053eb87b3d0cf97b5469fb837530";
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    
    console.log("$CYBR Pool:        ", cybrAddress);
    console.log("New GC (V9):       ", GC_V9);
    console.log("");

    const cybr = await ethers.getContractAt("BondingCurvePool", cybrAddress);
    
    // Check current state
    const currentGC = await cybr.graduationController();
    console.log("Current GC:        ", currentGC);
    
    if (currentGC.toLowerCase() === GC_V9.toLowerCase()) {
        console.log("\n✅ $CYBR already points to GC V9! Nothing to do.");
        return;
    }
    
    console.log("\n📝 Updating $CYBR.graduationController to GC V9...");
    
    const tx = await cybr.setGraduationController(GC_V9);
    console.log("Transaction sent:", tx.hash);
    
    const receipt = await tx.wait();
    console.log("✅ Transaction confirmed in block:", receipt.blockNumber);
    
    // Verify
    const newGC = await cybr.graduationController();
    console.log("\n🔍 VERIFICATION:");
    console.log("New GC address:    ", newGC);
    console.log("Match:             ", newGC.toLowerCase() === GC_V9.toLowerCase());
    
    if (newGC.toLowerCase() === GC_V9.toLowerCase()) {
        console.log("\n🎉 SUCCESS! $CYBR now points to GC V9!");
        console.log("\n📝 Next: Graduation monitor should now be able to initiate graduation for $CYBR");
    } else {
        console.log("\n❌ ERROR: Update failed!");
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("\n❌ Error:", error);
        process.exit(1);
    });
