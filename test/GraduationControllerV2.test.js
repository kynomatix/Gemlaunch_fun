import { expect } from "chai";
import hre from "hardhat";
const { ethers } = hre;
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";

describe("GraduationControllerV2 Price Calculations", function () {
  async function deployMockWKAS() {
    const MockWKAS = await ethers.getContractFactory("MockWKAS");
    const wkas = await MockWKAS.deploy();
    await wkas.waitForDeployment();
    return wkas;
  }

  async function deployMockPositionManager() {
    const MockPositionManager = await ethers.getContractFactory("MockPositionManager");
    const positionManager = await MockPositionManager.deploy();
    await positionManager.waitForDeployment();
    return positionManager;
  }

  async function deployGraduationControllerV2Fixture() {
    const [owner, oracle, treasury, airdropTreasury, platformDev, creator, user1, admin, buyback, kaspa, community] = await ethers.getSigners();

    const wkas = await deployMockWKAS();
    const positionManager = await deployMockPositionManager();

    const wkasAddress = await wkas.getAddress();
    const positionManagerAddress = await positionManager.getAddress();

    // Deploy GraduationControllerV2 FIRST (before TokenFactory)
    // Use owner address as placeholder for tokenFactory (will be updated after deployment)
    const GraduationControllerV2 = await ethers.getContractFactory("contracts/GraduationControllerV2.sol:GraduationController");
    const controller = await GraduationControllerV2.deploy(
      "0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8",
      positionManagerAddress,
      wkasAddress,
      oracle.address,
      owner.address  // Placeholder address for tokenFactory, will be updated below
    );
    await controller.waitForDeployment();

    // Deploy TokenFactory with all 9 required parameters
    const TokenFactory = await ethers.getContractFactory("TokenFactory");
    const tokenFactory = await TokenFactory.deploy(
      await controller.getAddress(),  // _graduationController
      treasury.address,               // _treasury
      airdropTreasury.address,       // _airdropTreasury
      platformDev.address,            // _platformDevelopmentWallet
      oracle.address,                 // _graduationOracle
      admin.address,                  // _admin
      buyback.address,                // _buybackReserve
      kaspa.address,                  // _kaspaSupport
      community.address               // _communityRewards
    );
    await tokenFactory.waitForDeployment();

    // Update controller with the actual tokenFactory address
    await controller.setTokenFactory(await tokenFactory.getAddress());

    const BondingCurvePool = await ethers.getContractFactory("BondingCurvePool");
    const totalSupply = ethers.parseEther("1000000");
    
    const pool = await BondingCurvePool.deploy(
      "Test Token",
      "TEST",
      totalSupply,
      creator.address,
      treasury.address,
      airdropTreasury.address,
      platformDev.address,
      false,
      await controller.getAddress(),
      admin.address,
      buyback.address,
      kaspa.address,
      community.address,
      0
    );
    await pool.waitForDeployment();

    const poolHigherAddress = await BondingCurvePool.deploy(
      "High Address Token",
      "HIGH",
      totalSupply,
      creator.address,
      treasury.address,
      airdropTreasury.address,
      platformDev.address,
      false,
      await controller.getAddress(),
      admin.address,
      buyback.address,
      kaspa.address,
      community.address,
      0
    );
    await poolHigherAddress.waitForDeployment();

    return {
      controller,
      pool,
      poolHigherAddress,
      wkas,
      positionManager,
      tokenFactory,
      owner,
      oracle,
      treasury,
      airdropTreasury,
      platformDev,
      creator,
      user1,
      totalSupply
    };
  }

  describe("sqrtPriceX96 Calculation Tests", function () {
    it("Test 1: Equal reserves (1:1 price ratio)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1000");
      const tokenReserve = ethers.parseEther("1000");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      const expected = BigInt(2) ** BigInt(96);
      
      console.log("Test 1 - Equal reserves (1:1):");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());
      console.log("  expected:", expected.toString());

      expect(sqrtPrice).to.equal(expected);
    });

    it("Test 2: Unequal reserves (KTR actual values)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1131.177");
      const tokenReserve = ethers.parseEther("574.62");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      const expected = BigInt("111161266831013092294972669952");
      const deviation = sqrtPrice > expected ? sqrtPrice - expected : expected - sqrtPrice;
      
      console.log("Test 2 - KTR actual values:");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  price ratio:", (Number(kasReserve) / Number(tokenReserve)).toFixed(4));
      console.log("  sqrtPriceX96:", sqrtPrice.toString());
      console.log("  expected:", expected.toString());
      console.log("  deviation:", deviation.toString());

      expect(deviation).to.be.lt(expected / BigInt(10000));
    });

    it("Test 3: High price (100:1)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("10000");
      const tokenReserve = ethers.parseEther("100");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      const expected = BigInt(10) * (BigInt(2) ** BigInt(96));
      
      console.log("Test 3 - High price (100:1):");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());
      console.log("  expected:", expected.toString());

      expect(sqrtPrice).to.equal(expected);
    });

    it("Test 4: Low price (1:100)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("100");
      const tokenReserve = ethers.parseEther("10000");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      const expected = (BigInt(2) ** BigInt(96)) / BigInt(10);
      
      console.log("Test 4 - Low price (1:100):");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());
      console.log("  expected:", expected.toString());

      expect(sqrtPrice).to.equal(expected);
    });

    it("Test 5: Reverse token ordering (WKAS < token)", async function () {
      const { controller, poolHigherAddress, wkas } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await poolHigherAddress.getAddress();
      const wkasAddress = await wkas.getAddress();

      const kasReserve = ethers.parseEther("1000");
      const tokenReserve = ethers.parseEther("2000");

      const isTokenLower = tokenAddress.toLowerCase() < wkasAddress.toLowerCase();

      console.log("Test 5 - Token ordering:");
      console.log("  tokenAddress:", tokenAddress);
      console.log("  wkasAddress:", wkasAddress);
      console.log("  isTokenLower:", isTokenLower);

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });

    it("Test 6: Edge case - very small reserves", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = BigInt(1);
      const tokenReserve = ethers.parseEther("1");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("Test 6 - Very small reserves:");
      console.log("  kasReserve:", kasReserve.toString(), "wei");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });

    it("Test 7: Validate sqrtPriceX96 format (Q64.96)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1000");
      const tokenReserve = ethers.parseEther("1000");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      const minValidPrice = BigInt(1);
      const maxValidPrice = (BigInt(2) ** BigInt(160)) - BigInt(1);

      console.log("Test 7 - Q64.96 format validation:");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());
      console.log("  minValidPrice:", minValidPrice.toString());
      console.log("  maxValidPrice:", maxValidPrice.toString());

      expect(sqrtPrice).to.be.gte(minValidPrice);
      expect(sqrtPrice).to.be.lte(maxValidPrice);
    });

    it("Test 8: REALISTIC PRODUCTION VALUES (KTR graduation scenario)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1131.177");
      const tokenReserve = ethers.parseEther("574.62");

      console.log("Test 8 - REALISTIC PRODUCTION VALUES:");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  kasReserve (wei):", kasReserve.toString());
      console.log("  tokenReserve (wei):", tokenReserve.toString());

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("  ✅ sqrtPriceX96:", sqrtPrice.toString());
      console.log("  Expected (approx):", "111161266831013092294972669952");

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);

      const expectedApprox = BigInt("111161266831013092294972669952");
      const deviation = sqrtPrice > expectedApprox ? sqrtPrice - expectedApprox : expectedApprox - sqrtPrice;
      const deviationPercent = (Number(deviation) / Number(expectedApprox)) * 100;
      
      console.log("  Deviation:", deviation.toString());
      console.log("  Deviation %:", deviationPercent.toFixed(4), "%");

      expect(deviationPercent).to.be.lt(0.1);
    });

    it("Test 9: MAXIMUM RESERVE VALUES (2M KAS graduation scenario)", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const maxKasReserve = ethers.parseEther("2000000");
      const maxTokenReserve = ethers.parseEther("1000000000");

      console.log("Test 9 - MAXIMUM RESERVE VALUES:");
      console.log("  maxKasReserve:", ethers.formatEther(maxKasReserve), "KAS");
      console.log("  maxTokenReserve:", ethers.formatEther(maxTokenReserve), "tokens");
      console.log("  maxKasReserve (wei):", maxKasReserve.toString());
      console.log("  maxTokenReserve (wei):", maxTokenReserve.toString());

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        maxKasReserve,
        maxTokenReserve,
        tokenAddress
      );

      console.log("  ✅ Max reserve sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);

      const priceRatio = Number(maxKasReserve) / Number(maxTokenReserve);
      console.log("  Price ratio:", priceRatio.toFixed(10));
      console.log("  Expected sqrt(ratio) * 2^96:", (Math.sqrt(priceRatio) * (2 ** 96)).toExponential(4));
    });
  });

  describe("Price Calculation Edge Cases", function () {
    it("Should revert with zero kasReserve", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      await expect(
        controller.calculateSqrtPriceX96(
          0,
          ethers.parseEther("1000"),
          tokenAddress
        )
      ).to.be.revertedWith("Invalid reserves");
    });

    it("Should revert with zero tokenReserve", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      await expect(
        controller.calculateSqrtPriceX96(
          ethers.parseEther("1000"),
          0,
          tokenAddress
        )
      ).to.be.revertedWith("Invalid reserves");
    });

    it("Should handle very large price ratios", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1000000");
      const tokenReserve = ethers.parseEther("1");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("Large price ratio test:");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });

    it("Should handle very small price ratios", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1");
      const tokenReserve = ethers.parseEther("1000000");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("Small price ratio test:");
      console.log("  kasReserve:", ethers.formatEther(kasReserve), "KAS");
      console.log("  tokenReserve:", ethers.formatEther(tokenReserve), "tokens");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });
  });

  describe("FullMath.mulDiv Overflow Protection", function () {
    it("Test 8 verification: No overflow with realistic values using FullMath", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const kasReserve = ethers.parseEther("1131.177");
      const tokenReserve = ethers.parseEther("574.62");

      console.log("FullMath overflow protection test (realistic values):");
      console.log("  kasReserve:", kasReserve.toString(), "wei");
      console.log("  Shifting by 192 bits would cause overflow without FullMath");
      console.log("  kasReserve << 192 ≈ 10^78 (exceeds uint256 max of 10^77)");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        kasReserve,
        tokenReserve,
        tokenAddress
      );

      console.log("  ✅ FullMath.mulDiv successfully handled the calculation");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });

    it("Test 9 verification: No overflow with maximum values using FullMath", async function () {
      const { controller, pool } = await loadFixture(deployGraduationControllerV2Fixture);
      const tokenAddress = await pool.getAddress();

      const maxKasReserve = ethers.parseEther("2000000");
      const maxTokenReserve = ethers.parseEther("1000000000");

      console.log("FullMath overflow protection test (maximum values):");
      console.log("  maxKasReserve:", maxKasReserve.toString(), "wei");
      console.log("  Direct shift would overflow: 2*10^24 << 192 ≈ 10^81");
      console.log("  FullMath handles this with 512-bit intermediate calculation");

      const sqrtPrice = await controller.calculateSqrtPriceX96(
        maxKasReserve,
        maxTokenReserve,
        tokenAddress
      );

      console.log("  ✅ FullMath.mulDiv successfully handled extreme values");
      console.log("  sqrtPriceX96:", sqrtPrice.toString());

      expect(sqrtPrice).to.be.gt(0);
      expect(sqrtPrice).to.be.lt(ethers.MaxUint256);
    });
  });

  describe("Deployment and Configuration", function () {
    it("Should deploy with correct version", async function () {
      const { controller } = await loadFixture(deployGraduationControllerV2Fixture);

      expect(await controller.VERSION()).to.equal("2.0.0");
      console.log("Contract version:", await controller.VERSION());
    });

    it("Should set correct immutable addresses", async function () {
      const { controller, wkas, positionManager } = await loadFixture(deployGraduationControllerV2Fixture);

      expect(await controller.kaspaFinanceFactory()).to.equal("0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8");
      expect(await controller.kaspaFinancePositionManager()).to.equal(await positionManager.getAddress());
      expect(await controller.kaspaFinanceWKAS()).to.equal(await wkas.getAddress());

      console.log("Kaspa Finance Factory:", await controller.kaspaFinanceFactory());
      console.log("Position Manager:", await controller.kaspaFinancePositionManager());
      console.log("WKAS:", await controller.kaspaFinanceWKAS());
    });

    it("Should set correct pool constants", async function () {
      const { controller } = await loadFixture(deployGraduationControllerV2Fixture);

      expect(await controller.POOL_FEE_TIER()).to.equal(2500);
      expect(await controller.FULL_RANGE_TICK_LOWER()).to.equal(-887220);
      expect(await controller.FULL_RANGE_TICK_UPPER()).to.equal(887220);
      expect(await controller.INITIAL_VIRTUAL_KAS()).to.equal(ethers.parseEther("1000"));
      expect(await controller.LP_SUPPLY_PERCENTAGE()).to.equal(25);

      console.log("Pool fee tier:", await controller.POOL_FEE_TIER());
      console.log("Full range ticks:", await controller.FULL_RANGE_TICK_LOWER(), "to", await controller.FULL_RANGE_TICK_UPPER());
    });
  });
});
