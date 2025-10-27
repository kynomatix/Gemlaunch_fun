import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    const cybrAddress = "0x7da3452a3c51053eb87b3d0cf97b5469fb837530"; // $CYBR pool
    
    const pool = await ethers.getContractAt("BondingCurvePool", cybrAddress);
    const factoryAddress = await pool.factory();
    
    console.log("$CYBR Pool:", cybrAddress);
    console.log("factory() stored in pool:", factoryAddress);
    console.log("");
    console.log("Expected TokenFactory V11:", "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1");
    console.log("Match:", factoryAddress.toLowerCase() === "0x427b039bc381911a40ac25fc50ab9e6f5633a5b1");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
