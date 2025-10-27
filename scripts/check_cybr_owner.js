import pkg from 'hardhat';
const { ethers } = pkg;

async function main() {
    const cybr = await ethers.getContractAt("BondingCurvePool", "0x7da3452a3c51053eb87b3d0cf97b5469fb837530");
    const owner = await cybr.owner();
    console.log("$CYBR owner:", owner);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
