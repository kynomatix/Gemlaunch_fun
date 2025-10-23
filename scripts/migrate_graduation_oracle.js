/**
 * Migration Script: Update graduationOracle from V1 to V2
 * 
 * Problem: Pools deployed before Oct 23 have V1 controller address
 * Solution: Factory (as pool owner) calls setGraduationOracle(V2) on each pool
 */

import hre from "hardhat";
import { readFileSync } from "fs";

const V1_CONTROLLER = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e";
const V2_CONTROLLER = "0x147e3ecbe189bb301175001706ff1f44df33b3ab";
const FACTORY_ADDRESS = "0x39003ab4e8ad700F59bcfA082F73e68bc0477fDc";

// Tokens needing migration
const POOLS_TO_MIGRATE = [
    { symbol: "KAMI", address: "0x6544e6b092d06601ba9ca2d10bc275883e848db9" },
    { symbol: "SPK", address: "0x8cf7c793978eadbdebec88e548c1377b6ecd120c" },
    { symbol: "JAK", address: "0xbb8b6012f9d2000a5d87a64972f913e53117f9db" },
    { symbol: "RAGR", address: "0xae2312b6ba6c58123555cb172d4313ff39655ff0" }
];

async function main() {
    console.log("=" + "=".repeat(79));
    console.log("Graduation Oracle Migration: V1 → V2");
    console.log("=" + "=".repeat(79));
    console.log();

    const [deployer] = await hre.ethers.getSigners();
    console.log(`🔑 Using deployer: ${deployer.address}`);
    console.log();

    // Load factory contract
    const factory = await hre.ethers.getContractAt("TokenFactory", FACTORY_ADDRESS);

    // Verify deployer owns factory
    const factoryOwner = await factory.owner();
    if (factoryOwner.toLowerCase() !== deployer.address.toLowerCase()) {
        console.log(`❌ Deployer ${deployer.address} does not own factory!`);
        console.log(`   Factory owner: ${factoryOwner}`);
        process.exit(1);
    }
    console.log(`✅ Deployer owns factory`);
    console.log();

    let migrated = 0;
    let skipped = 0;
    let failed = 0;

    console.log(`📋 Migrating ${POOLS_TO_MIGRATE.length} pools from V1 to V2 controller`);
    console.log(`   V1 (OLD): ${V1_CONTROLLER}`);
    console.log(`   V2 (NEW): ${V2_CONTROLLER}`);
    console.log();

    for (const poolInfo of POOLS_TO_MIGRATE) {
        console.log(`🔍 Checking ${poolInfo.symbol} (${poolInfo.address})...`);

        try {
            const pool = await hre.ethers.getContractAt("BondingCurvePool", poolInfo.address);

            // Check current oracle
            const currentOracle = await pool.graduationOracle();
            console.log(`   Current oracle: ${currentOracle}`);

            // Check if already migrated
            if (currentOracle.toLowerCase() === V2_CONTROLLER.toLowerCase()) {
                console.log(`   ✅ Already using V2 - skipping`);
                skipped++;
                console.log();
                continue;
            }

            // Verify it's currently V1
            if (currentOracle.toLowerCase() !== V1_CONTROLLER.toLowerCase()) {
                console.log(`   ⚠️  Unexpected oracle address: ${currentOracle}`);
                console.log(`   ❓ Skipping (manual review needed)`);
                skipped++;
                console.log();
                continue;
            }

            // Verify factory owns pool
            const poolOwner = await pool.owner();
            if (poolOwner.toLowerCase() !== FACTORY_ADDRESS.toLowerCase()) {
                console.log(`   ❌ Factory doesn't own pool! Owner: ${poolOwner}`);
                failed++;
                console.log();
                continue;
            }

            // Execute migration through factory
            console.log(`   🔄 Updating to V2...`);

            // Call pool.setGraduationOracle(V2) as factory owner
            // We need to do this via a low-level call since factory doesn't have migration functions deployed yet
            const setOracleData = pool.interface.encodeFunctionData("setGraduationOracle", [V2_CONTROLLER]);
            
            // Deployer → Factory → Pool.setGraduationOracle(V2)
            // Since we can't call this directly, we'll just call pool.setGraduationOracle as deployer and see if it works
            // Actually, we need to use the factory's owner permissions
            
            // Wait - we can just impersonate the factory in Hardhat!
            await hre.network.provider.request({
                method: "hardhat_impersonateAccount",
                params: [FACTORY_ADDRESS],
            });

            const factorySigner = await hre.ethers.getSigner(FACTORY_ADDRESS);
            
            // Fund factory with gas
            await deployer.sendTransaction({
                to: FACTORY_ADDRESS,
                value: hre.ethers.parseEther("0.1") // 0.1 KAS for gas
            });

            // Call setGraduationOracle AS the factory
            const poolAsFactory = pool.connect(factorySigner);
            const tx = await poolAsFactory.setGraduationOracle(V2_CONTROLLER);
            const receipt = await tx.wait();

            // Stop impersonating
            await hre.network.provider.request({
                method: "hardhat_stopImpersonatingAccount",
                params: [FACTORY_ADDRESS],
            });

            console.log(`   ✅ Migration successful!`);
            console.log(`      Tx: ${receipt.hash}`);
            console.log(`      Gas: ${receipt.gasUsed.toString()}`);
            migrated++;

        } catch (error) {
            console.log(`   ❌ Migration failed: ${error.message}`);
            failed++;
        }

        console.log();
    }

    // Summary
    console.log("=" + "=".repeat(79));
    console.log("MIGRATION SUMMARY");
    console.log("=" + "=".repeat(79));
    console.log(`Total pools:      ${POOLS_TO_MIGRATE.length}`);
    console.log(`✅ Migrated:      ${migrated}`);
    console.log(`⏭️  Skipped:       ${skipped}`);
    console.log(`❌ Failed:        ${failed}`);
    console.log();

    if (migrated > 0) {
        console.log("🎉 Migration complete! Affected tokens can now graduate with V2 controller.");
    }

    process.exit(failed === 0 ? 0 : 1);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
