import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    const crnchAddress = "0x6aba77de0bd17062287778e8502d822b473d8d1c";

    console.log("\n" + "=".repeat(80));
    console.log("🔍 VERIFYING $CRNCH CONFIGURATION");
    console.log("=".repeat(80) + "\n");

    const crnch = await ethers.getContractAt("BondingCurvePool", crnchAddress);
    
    const factory = await crnch.factory();
    const gc = await crnch.graduationController();
    
    console.log("$CRNCH Pool:                ", crnchAddress);
    console.log("factory():                  ", factory);
    console.log("graduationController():     ", gc);
    console.log("");
    
    const TF_V11 = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1";
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    
    const factoryCorrect = factory.toLowerCase() === TF_V11.toLowerCase();
    const gcCorrect = gc.toLowerCase() === GC_V9.toLowerCase();
    
    console.log("=".repeat(80));
    console.log("VERIFICATION:");
    console.log("=".repeat(80));
    console.log("✓ Created by TF V11:        ", factoryCorrect ? "✅ YES" : "❌ NO");
    console.log("✓ Has GC V9 embedded:       ", gcCorrect ? "✅ YES" : "❌ NO");
    console.log("");
    
    if (factoryCorrect && gcCorrect) {
        console.log("🎉 SUCCESS! $CRNCH has the correct configuration!");
        console.log("");
        console.log("📝 Next steps:");
        console.log("   1. Buy $CRNCH to reach $50 market cap");
        console.log("   2. Graduation monitor will detect it automatically");
        console.log("   3. Monitor will call $CRNCH.initiateGraduation()");
        console.log("   4. $CRNCH calls GC V9 (correct!)");
        console.log("   5. GC V9 verifies with TF V11 (should pass!)");
        console.log("");
        console.log("🚀 This should be the FIRST successful graduation!");
    } else {
        console.log("❌ ERROR: Configuration mismatch!");
        if (!factoryCorrect) {
            console.log("   Factory is:", factory);
            console.log("   Expected:  ", TF_V11);
        }
        if (!gcCorrect) {
            console.log("   GC is:     ", gc);
            console.log("   Expected:  ", GC_V9);
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("\n❌ Error:", error);
        process.exit(1);
    });
