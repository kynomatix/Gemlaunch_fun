import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    const tfAddress = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1"; // TokenFactory V11
    
    const tf = await ethers.getContractAt("TokenFactory", tfAddress);
    const gcAddress = await tf.graduationController();
    
    console.log("TokenFactory V11:", tfAddress);
    console.log("graduationController():", gcAddress);
    console.log("");
    console.log("Expected GC V9:", "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6");
    console.log("Match:", gcAddress.toLowerCase() === "0xac022ab0860d3d7d5a8738cd6bf58090117cc7f6");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
