import hre from "hardhat";

const errors = [
    "OnlyOracle()",
    "AlreadyGraduated()",
    "AlreadyInitiated()",
    "NotInitiated()",
    "InvalidToken()",
    "InsufficientLiquidity()",
    "InvalidPrice()",
    "PoolNotReady()",
    "TransferFailed()",
    "InvalidAddress()",
    "UnauthorizedOracle()"
];

const targetSelector = "0xdb8d1fb7";

console.log("Decoding error selector:", targetSelector);
console.log("");

for (const error of errors) {
    const selector = hre.ethers.id(error).slice(0, 10);
    const match = selector.toLowerCase() === targetSelector.toLowerCase() ? " ✅ MATCH!" : "";
    console.log(`${error.padEnd(30)} ${selector}${match}`);
}
