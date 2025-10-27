import { ethers } from "hardhat";

async function main() {
    console.log("Updating GraduationController to V4...");
    
    const [deployer] = await ethers.getSigners();
    console.log("Using account:", deployer.address);
    
    const GC_V4 = "0x01Be48DeA4a1a8e4D625E6C2f253D05ebdb59031";
    const TOKEN_FACTORY = "0xDe2a7Ef9A8e29EDF2f6A16a3Ca6fe512E88c9211";
    const KREX_POOL = "0x14F6B3Bde14EA40Ec0321Cdfb7208740D8903647";
    
    console.log("\n=== Update 1: TokenFactory → V4 ===");
    console.log("This will make all FUTURE tokens use V4");
    
    const factoryArtifact = await ethers.getContractFactory("TokenFactory");
    const factory = factoryArtifact.attach(TOKEN_FACTORY);
    
    // Check current GC
    const currentGC = await factory.graduationController();
    console.log("Current GC:", currentGC);
    console.log("Target GC V4:", GC_V4);
    
    if (currentGC.toLowerCase() === GC_V4.toLowerCase()) {
        console.log("✅ Already using V4!");
    } else {
        console.log("Calling factory.setGraduationController()...");
        const tx1 = await factory.setGraduationController(GC_V4);
        console.log("TX submitted:", tx1.hash);
        await tx1.wait();
        console.log("✅ TokenFactory updated to V4!");
    }
    
    console.log("\n=== Update 2: KREX Pool → V4 ===");
    console.log("This will make KREX specifically use V4");
    
    const poolArtifact = await ethers.getContractFactory("BondingCurvePool");
    const krexPool = poolArtifact.attach(KREX_POOL);
    
    // Check current GC in KREX pool
    const krexCurrentGC = await krexPool.graduationController();
    console.log("KREX current GC:", krexCurrentGC);
    console.log("Target GC V4:", GC_V4);
    
    if (krexCurrentGC.toLowerCase() === GC_V4.toLowerCase()) {
        console.log("✅ KREX already using V4!");
    } else {
        console.log("Calling krexPool.setGraduationController()...");
        const tx2 = await krexPool.setGraduationController(GC_V4);
        console.log("TX submitted:", tx2.hash);
        await tx2.wait();
        console.log("✅ KREX pool updated to V4!");
    }
    
    console.log("\n=== Verification ===");
    const finalFactoryGC = await factory.graduationController();
    const finalKrexGC = await krexPool.graduationController();
    
    console.log("TokenFactory GC:", finalFactoryGC);
    console.log("KREX Pool GC:", finalKrexGC);
    
    if (finalFactoryGC.toLowerCase() === GC_V4.toLowerCase() && 
        finalKrexGC.toLowerCase() === GC_V4.toLowerCase()) {
        console.log("\n🎉 All contracts successfully updated to V4!");
        console.log("\n✅ KREX is now safe to fund and will use the correct graduation flow");
    } else {
        console.log("\n❌ Something went wrong - verification failed");
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
