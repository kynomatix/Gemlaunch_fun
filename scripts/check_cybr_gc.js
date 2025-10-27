import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    const cybrAddress = "0x7da3452a3c51053eb87b3d0cf97b5469fb837530";
    
    const cybr = await ethers.getContractAt("BondingCurvePool", cybrAddress);
    const cybrGC = await cybr.graduationController();
    
    console.log("$CYBR Pool:                ", cybrAddress);
    console.log("graduationController():    ", cybrGC);
    console.log("");
    console.log("Expected GC V9:            ", "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6");
    console.log("Actual is GC V8:           ", cybrGC.toLowerCase() === "0x22f3cc689401462b6ceb85ef544e86fe27ad178f");
    console.log("Actual is GC V9:           ", cybrGC.toLowerCase() === "0xac022ab0860d3d7d5a8738cd6bf58090117cc7f6");
    
    if (cybrGC.toLowerCase() === "0x22f3cc689401462b6ceb85ef544e86fe27ad178f") {
        console.log("");
        console.log("🚨 ROOT CAUSE FOUND:");
        console.log("   $CYBR pool is configured to call GC V8!");
        console.log("   GC V8's tokenFactory is TokenFactory V10, not V11!");
        console.log("   That's why validation fails!");
        
        const gcV8 = await ethers.getContractAt("GraduationControllerV3", cybrGC);
        const gcV8Factory = await gcV8.tokenFactory();
        console.log("");
        console.log("GC V8 tokenFactory:        ", gcV8Factory);
        console.log("$CYBR's factory:           ", await cybr.factory());
        console.log("Match:                     ", gcV8Factory.toLowerCase() === (await cybr.factory()).toLowerCase());
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
