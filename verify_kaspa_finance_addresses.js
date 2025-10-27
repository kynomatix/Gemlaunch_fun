import hre from "hardhat";
import fs from 'fs';

async function main() {
    const GC_V9 = "0xaC022Ab0860D3D7D5A8738cd6BF58090117CC7f6";
    
    // Load deployed addresses
    const deployed = JSON.parse(fs.readFileSync('contracts/deployed_addresses.json', 'utf8'));
    const kf = deployed.externalContracts.KaspaFinance;
    
    console.log("Expected Kaspa Finance Addresses:");
    console.log("=================================");
    console.log(`Factory:         ${kf.Factory}`);
    console.log(`Position Mgr:    ${kf.PositionManager}`);
    console.log(`WKAS:            ${kf.WKAS}`);
    
    const gcAbi = [
        "function kaspaFinanceFactory() view returns (address)",
        "function kaspaFinancePositionManager() view returns (address)",
        "function kaspaFinanceWKAS() view returns (address)"
    ];
    
    const gc = await hre.ethers.getContractAt(gcAbi, GC_V9);
    
    const actualFactory = await gc.kaspaFinanceFactory();
    const actualPM = await gc.kaspaFinancePositionManager();
    const actualWKAS = await gc.kaspaFinanceWKAS();
    
    console.log("\nActual GC V9 Addresses:");
    console.log("======================");
    console.log(`Factory:         ${actualFactory}`);
    console.log(`Position Mgr:    ${actualPM}`);
    console.log(`WKAS:            ${actualWKAS}`);
    
    console.log("\nVerification:");
    console.log("=============");
    console.log(`Factory:      ${actualFactory.toLowerCase() === kf.Factory.toLowerCase() ? '✅ MATCH' : '❌ MISMATCH'}`);
    console.log(`Position Mgr: ${actualPM.toLowerCase() === kf.PositionManager.toLowerCase() ? '✅ MATCH' : '❌ MISMATCH'}`);
    console.log(`WKAS:         ${actualWKAS.toLowerCase() === kf.WKAS.toLowerCase() ? '✅ MATCH' : '❌ MISMATCH'}`);
    
    // Check if contracts exist
    console.log("\nContract Existence:");
    console.log("==================");
    const factoryCode = await hre.ethers.provider.getCode(actualFactory);
    const pmCode = await hre.ethers.provider.getCode(actualPM);
    const wkasCode = await hre.ethers.provider.getCode(actualWKAS);
    
    console.log(`Factory exists:      ${factoryCode !== '0x' ? '✅ Yes' : '❌ No'} (${factoryCode.length} bytes)`);
    console.log(`Position Mgr exists: ${pmCode !== '0x' ? '✅ Yes' : '❌ No'} (${pmCode.length} bytes)`);
    console.log(`WKAS exists:         ${wkasCode !== '0x' ? '✅ Yes' : '❌ No'} (${wkasCode.length} bytes)`);
}

main().catch(console.error);
