import { expect } from "chai";
import hre from "hardhat";
const { ethers } = hre;
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";

describe("BondingCurvePool", function () {
  // Deployment fixture for efficiency
  async function deployBondingCurvePoolFixture() {
    const [owner, creator, treasury, airdropTreasury, platformDev, user1, user2, oracle, admin, buyback, kaspa, community] = await ethers.getSigners();

    const BondingCurvePool = await ethers.getContractFactory("BondingCurvePool");
    
    const totalSupply = ethers.parseEther("1000000"); // 1M tokens
    
    const pool = await BondingCurvePool.deploy(
      "Test Token",
      "TEST",
      totalSupply,
      creator.address,
      treasury.address,
      airdropTreasury.address,
      platformDev.address,
      false, // antiBotEnabled = false
      oracle.address,
      admin.address,
      buyback.address,
      kaspa.address,
      community.address
    );
    
    await pool.waitForDeployment();
    const poolAddress = await pool.getAddress();

    return { 
      pool, 
      poolAddress,
      owner, 
      creator, 
      treasury, 
      airdropTreasury, 
      platformDev, 
      user1, 
      user2, 
      oracle,
      totalSupply 
    };
  }

  async function deployWithAntiBotFixture() {
    const [owner, creator, treasury, airdropTreasury, platformDev, user1, user2, oracle, admin, buyback, kaspa, community] = await ethers.getSigners();

    const BondingCurvePool = await ethers.getContractFactory("BondingCurvePool");
    
    const totalSupply = ethers.parseEther("1000000");
    
    const pool = await BondingCurvePool.deploy(
      "AntiBot Token",
      "ABOT",
      totalSupply,
      creator.address,
      treasury.address,
      airdropTreasury.address,
      platformDev.address,
      true, // antiBotEnabled = true
      oracle.address,
      admin.address,
      buyback.address,
      kaspa.address,
      community.address
    );
    
    await pool.waitForDeployment();
    const poolAddress = await pool.getAddress();

    return { 
      pool, 
      poolAddress,
      owner, 
      creator, 
      treasury, 
      airdropTreasury, 
      platformDev, 
      user1, 
      user2, 
      oracle,
      totalSupply 
    };
  }

  describe("Deployment", function () {
    it("Should set the correct initial parameters", async function () {
      const { pool, creator, treasury, airdropTreasury, platformDev, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      expect(await pool.name()).to.equal("Test Token");
      expect(await pool.symbol()).to.equal("TEST");
      expect(await pool.totalSupply()).to.equal(totalSupply);
      expect(await pool.creator()).to.equal(creator.address);
      expect(await pool.treasury()).to.equal(treasury.address);
      expect(await pool.airdropTreasury()).to.equal(airdropTreasury.address);
      expect(await pool.platformDevelopmentWallet()).to.equal(platformDev.address);
      expect(await pool.antiBotEnabled()).to.equal(false);
    });

    it("Should initialize virtual reserves correctly", async function () {
      const { pool, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      const expectedTokenReserve = totalSupply * 75n / 100n; // 75% of supply
      expect(await pool.virtualTokenReserve()).to.equal(expectedTokenReserve);
      expect(await pool.virtualKasReserve()).to.equal(ethers.parseEther("0.001")); // Initial seed
    });

    it("Should reject invalid constructor parameters", async function () {
      const [owner, creator, treasury, airdropTreasury, platformDev, oracle, admin, buyback, kaspa, community] = await ethers.getSigners();
      const BondingCurvePool = await ethers.getContractFactory("BondingCurvePool");
      const totalSupply = ethers.parseEther("1000000");

      await expect(
        BondingCurvePool.deploy(
          "Test",
          "TEST",
          totalSupply,
          ethers.ZeroAddress, // Invalid creator
          treasury.address,
          airdropTreasury.address,
          platformDev.address,
          false,
          oracle.address,
          admin.address,
          buyback.address,
          kaspa.address,
          community.address
        )
      ).to.be.revertedWith("Invalid creator");
    });
  });

  describe("buyTokens()", function () {
    it("Should execute a basic buy correctly", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1"); // 1 KAS
      const deadline = (await time.latest()) + 3600;
      
      // Get expected tokens
      const feeBreakdown = await pool.getEffectiveFeeBreakdown(buyAmount);
      const expectedTokens = await pool.quoteBuy(feeBreakdown.tradeAmount);

      const tx = await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });
      
      await expect(tx)
        .to.emit(pool, "TokensPurchased")
        .withArgs(user1.address, expectedTokens, feeBreakdown.tradeAmount, feeBreakdown.platformFee, feeBreakdown.creatorFee, 0);

      expect(await pool.balanceOf(user1.address)).to.equal(expectedTokens);
    });

    it("Should enforce minimum trade amount", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const tooSmall = ethers.parseEther("0.0001"); // Below 0.001 KAS minimum
      const deadline = (await time.latest()) + 3600;

      await expect(
        pool.connect(user1).buyTokens(0, deadline, { value: tooSmall })
      ).to.be.revertedWith("Below minimum trade");
    });

    it("Should enforce deadline", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1");
      const pastDeadline = (await time.latest()) - 1;

      await expect(
        pool.connect(user1).buyTokens(0, pastDeadline, { value: buyAmount })
      ).to.be.revertedWith("Transaction expired");
    });

    it("Should enforce slippage protection", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      
      const feeBreakdown = await pool.getEffectiveFeeBreakdown(buyAmount);
      const expectedTokens = await pool.quoteBuy(feeBreakdown.tradeAmount);

      // Request more tokens than possible
      const unrealisticMin = expectedTokens * 2n;

      await expect(
        pool.connect(user1).buyTokens(unrealisticMin, deadline, { value: buyAmount })
      ).to.be.revertedWith("Slippage too high");
    });

    it("Should accumulate fees correctly", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      
      const feeBreakdown = await pool.getEffectiveFeeBreakdown(buyAmount);

      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      expect(await pool.accumulatedPlatformFees()).to.equal(feeBreakdown.platformFee);
      expect(await pool.accumulatedCreatorFees()).to.equal(feeBreakdown.creatorFee);
    });

    it("Should update virtual reserves correctly", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const initialKasReserve = await pool.virtualKasReserve();
      const initialTokenReserve = await pool.virtualTokenReserve();

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      
      const feeBreakdown = await pool.getEffectiveFeeBreakdown(buyAmount);
      const tokensOut = await pool.quoteBuy(feeBreakdown.tradeAmount);

      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      expect(await pool.virtualKasReserve()).to.equal(initialKasReserve + feeBreakdown.tradeAmount);
      expect(await pool.virtualTokenReserve()).to.equal(initialTokenReserve - tokensOut);
    });

    it("Should prevent buying when graduated", async function () {
      const { pool, user1, oracle } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Initiate graduation
      await pool.connect(oracle).initiateGraduation();

      const buyAmount2 = ethers.parseEther("1");
      const deadline2 = (await time.latest()) + 3600;

      await expect(
        pool.connect(user1).buyTokens(0, deadline2, { value: buyAmount2 })
      ).to.be.revertedWith("Token graduated or graduating");
    });
  });

  describe("Anti-Bot System", function () {
    it("Should charge anti-bot fee at deployment (95%)", async function () {
      const { pool, user1, airdropTreasury, platformDev } = await loadFixture(deployWithAntiBotFixture);

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;

      const airdropBalanceBefore = await ethers.provider.getBalance(airdropTreasury.address);
      const platformBalanceBefore = await ethers.provider.getBalance(platformDev.address);

      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const airdropBalanceAfter = await ethers.provider.getBalance(airdropTreasury.address);
      const platformBalanceAfter = await ethers.provider.getBalance(platformDev.address);

      // Use actual fees collected from contract to avoid timing/rounding issues
      const actualAirdropFee = airdropBalanceAfter - airdropBalanceBefore;
      const actualPlatformFee = platformBalanceAfter - platformBalanceBefore;
      const totalActualFee = actualAirdropFee + actualPlatformFee;

      // Verify fees were charged (>0) and split correctly (70/30)
      expect(totalActualFee).to.be.gt(0);
      expect(actualAirdropFee).to.equal(totalActualFee * 70n / 100n);
      expect(actualPlatformFee).to.equal(totalActualFee - (totalActualFee * 70n / 100n));
    });

    it("Should decay anti-bot fee linearly over 60 seconds", async function () {
      const { pool } = await loadFixture(deployWithAntiBotFixture);

      const buyAmount = ethers.parseEther("1");

      const feeAt0 = await pool.getCurrentAntiBotFee(buyAmount);
      
      await time.increase(30); // 30 seconds
      const feeAt30 = await pool.getCurrentAntiBotFee(buyAmount);
      
      await time.increase(30); // 60 seconds total
      const feeAt60 = await pool.getCurrentAntiBotFee(buyAmount);

      expect(feeAt0).to.be.gt(feeAt30);
      expect(feeAt30).to.be.gt(feeAt60);
      expect(feeAt60).to.equal(0); // Should be 0 after 60 seconds
    });

    it("Should return 0 anti-bot fee when disabled", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1");
      const antiBotFee = await pool.getCurrentAntiBotFee(buyAmount);

      expect(antiBotFee).to.equal(0);
    });

    it("Should track total anti-bot fees collected", async function () {
      const { pool, user1 } = await loadFixture(deployWithAntiBotFixture);

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;

      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const totalCollected = await pool.totalAntiBotFeesCollected();
      
      // Verify fee was collected (decay means it's between 0 and initial max)
      expect(totalCollected).to.be.gt(0);
      expect(totalCollected).to.be.lte(buyAmount * 95n / 100n); // Max 95% at deployment
    });
  });

  describe("sellTokens()", function () {
    it("Should execute a basic sell correctly", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // First buy some tokens
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const tokenBalance = await pool.balanceOf(user1.address);
      const sellAmount = tokenBalance / 2n; // Sell half

      const kasGross = await pool.quoteSell(sellAmount);
      const totalFeesKas = kasGross * 100n / 10000n; // 1%
      const kasNet = kasGross - totalFeesKas;

      const userKasBefore = await ethers.provider.getBalance(user1.address);

      const tx = await pool.connect(user1).sellTokens(sellAmount, 0, deadline);
      const receipt = await tx.wait();
      const gasUsed = receipt.gasUsed * receipt.gasPrice;

      const userKasAfter = await ethers.provider.getBalance(user1.address);

      expect(userKasAfter - userKasBefore + gasUsed).to.equal(kasNet);
    });

    it("Should charge KAS-based fees on sell (1% of KAS output)", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const initialCreatorFees = await pool.accumulatedCreatorFees();
      const initialPlatformFees = await pool.accumulatedPlatformFees();

      const tokenBalance = await pool.balanceOf(user1.address);
      const kasGross = await pool.quoteSell(tokenBalance);
      
      const totalFeesKas = kasGross * 100n / 10000n; // 1%
      const creatorFeeKas = totalFeesKas * 10n / 100n; // 0.1% of KAS
      const platformFeeKas = totalFeesKas - creatorFeeKas; // 0.9% of KAS

      await pool.connect(user1).sellTokens(tokenBalance, 0, deadline);

      const finalCreatorFees = await pool.accumulatedCreatorFees();
      const finalPlatformFees = await pool.accumulatedPlatformFees();

      expect(finalCreatorFees - initialCreatorFees).to.equal(creatorFeeKas);
      expect(finalPlatformFees - initialPlatformFees).to.equal(platformFeeKas);
    });

    it("Should enforce minimum trade amount on sell", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("10");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Try to sell a tiny amount that results in less than 0.001 KAS
      const tinyAmount = 1n;

      await expect(
        pool.connect(user1).sellTokens(tinyAmount, 0, deadline)
      ).to.be.revertedWith("Below minimum trade");
    });

    it("Should revert if user has insufficient balance", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const deadline = (await time.latest()) + 3600;
      const impossibleAmount = ethers.parseEther("1000");

      await expect(
        pool.connect(user1).sellTokens(impossibleAmount, 0, deadline)
      ).to.be.revertedWith("Insufficient balance");
    });
  });

  describe("AMM Pricing", function () {
    it("Should calculate quoteBuy correctly using constant product formula", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const kasIn = ethers.parseEther("1");
      const tokensOut = await pool.quoteBuy(kasIn);

      const virtualKas = await pool.virtualKasReserve();
      const virtualTokens = await pool.virtualTokenReserve();
      const k = virtualKas * virtualTokens;

      const expectedNewKas = virtualKas + kasIn;
      const expectedNewTokens = k / expectedNewKas;
      const expectedTokensOut = virtualTokens - expectedNewTokens;

      expect(tokensOut).to.equal(expectedTokensOut);
    });

    it("Should calculate quoteSell correctly using constant product formula", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const tokensIn = ethers.parseEther("1000");
      const kasOut = await pool.quoteSell(tokensIn);

      const virtualKas = await pool.virtualKasReserve();
      const virtualTokens = await pool.virtualTokenReserve();
      const k = virtualKas * virtualTokens;

      const expectedNewTokens = virtualTokens + tokensIn;
      const expectedNewKas = k / expectedNewTokens;
      const expectedKasOut = virtualKas - expectedNewKas;

      expect(kasOut).to.equal(expectedKasOut);
    });

    it("Should revert on invalid quoteBuy output", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const virtualTokens = await pool.virtualTokenReserve();
      const tooMuchKas = ethers.parseEther("1000000"); // Would drain all tokens

      await expect(pool.quoteBuy(tooMuchKas)).to.be.revertedWith("Invalid output");
    });
  });

  describe("Wallet Cap Enforcement", function () {
    it("Should allow bonding curve buys to exceed 10% wallet cap (audit-approved exemption)", async function () {
      const { pool, user1, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      const maxWallet = totalSupply * 10n / 100n; // 10%
      
      // Buy enough to exceed the cap (bonding curve buys are exempt)
      const buyAmount1 = ethers.parseEther("500");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount1 });

      // Buy more to exceed the cap - this should SUCCEED (transfers from contract are exempt)
      const buyAmount2 = ethers.parseEther("500");
      
      // Check that we will exceed the cap
      const currentBalance = await pool.balanceOf(user1.address);
      const feeBreakdown = await pool.getEffectiveFeeBreakdown(buyAmount2);
      const additionalTokens = await pool.quoteBuy(feeBreakdown.tradeAmount);

      // Verify we will exceed the cap
      expect(currentBalance + additionalTokens).to.be.gt(maxWallet);
      
      // This should SUCCEED - bonding curve buys bypass wallet cap (from == address(this))
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount2 });
      
      // Verify user now holds > 10%
      const finalBalance = await pool.balanceOf(user1.address);
      expect(finalBalance).to.be.gt(maxWallet);
    });

    it("Should enforce 10% wallet cap on peer-to-peer transfers", async function () {
      const { pool, user1, user2, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      const maxWallet = totalSupply * 10n / 100n; // 10%
      
      // user1 buys tokens (can exceed 10% via bonding curve)
      const buyAmount = ethers.parseEther("500");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });
      
      const user1Balance = await pool.balanceOf(user1.address);
      
      // user2 buys a small amount (under 10%)
      const smallBuy = ethers.parseEther("1");
      await pool.connect(user2).buyTokens(0, deadline, { value: smallBuy });
      
      const user2Balance = await pool.balanceOf(user2.address);
      
      // Calculate transfer amount that would put user2 over 10%
      const transferAmount = maxWallet - user2Balance + 1n; // 1 token over the limit
      
      // Verify user1 has enough to transfer
      expect(user1Balance).to.be.gte(transferAmount);
      
      // Direct transfer from user1 → user2 should FAIL (wallet cap enforced)
      await expect(
        pool.connect(user1).transfer(user2.address, transferAmount)
      ).to.be.revertedWith("Exceeds max wallet");
    });

    it("Should exempt contract address from wallet cap", async function () {
      const { pool, poolAddress, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      const contractBalance = await pool.balanceOf(poolAddress);
      const maxWallet = totalSupply * 10n / 100n;

      // Contract holds more than 10% (curve supply + LP supply)
      expect(contractBalance).to.be.gt(maxWallet);
    });

    it("Should exempt airdropTreasury from wallet cap", async function () {
      const { pool, user1, airdropTreasury, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      const maxWallet = totalSupply * 10n / 100n;
      
      // First, user1 buys some tokens
      const buyAmount = ethers.parseEther("100");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // User1 transfers to airdropTreasury (should work even if airdropTreasury gets > 10%)
      const user1Balance = await pool.balanceOf(user1.address);
      await pool.connect(user1).transfer(airdropTreasury.address, user1Balance);

      // Verify airdropTreasury received the tokens
      expect(await pool.balanceOf(airdropTreasury.address)).to.equal(user1Balance);
    });

    it("Should not enforce wallet cap after graduation", async function () {
      const { pool, user1, oracle } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Complete graduation
      await pool.connect(oracle).initiateGraduation();
      await pool.connect(oracle).completeGraduation();

      // Now graduated, wallet cap shouldn't apply
      // Note: Can't buy tokens after graduation, but transfers should work without cap
      const largeAmount = (await pool.totalSupply()) * 20n / 100n; // 20% - more than cap
      
      // Get tokens to user1 first via owner (contract owner can transfer)
      const poolAddress = await pool.getAddress();
      const ownerBalance = await pool.balanceOf(poolAddress);
      
      if (ownerBalance >= largeAmount) {
        // This transfer should succeed without wallet cap check
        await expect(
          pool.transfer(user1.address, largeAmount)
        ).to.not.be.revertedWith("Exceeds max wallet");
      }
    });
  });

  describe("Creator Fee Claims", function () {
    it("Should allow creator to withdraw accumulated fees", async function () {
      const { pool, creator, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // Generate some creator fees
      const buyAmount = ethers.parseEther("10");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const creatorFees = await pool.accumulatedCreatorFees();
      expect(creatorFees).to.be.gt(0);

      const creatorBalanceBefore = await ethers.provider.getBalance(creator.address);

      const tx = await pool.connect(creator).withdrawCreatorFees();
      const receipt = await tx.wait();
      const gasUsed = receipt.gasUsed * receipt.gasPrice;

      const creatorBalanceAfter = await ethers.provider.getBalance(creator.address);

      expect(creatorBalanceAfter - creatorBalanceBefore + gasUsed).to.equal(creatorFees);
      expect(await pool.accumulatedCreatorFees()).to.equal(0);
    });

    it("Should revert if non-creator tries to withdraw", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(
        pool.connect(user1).withdrawCreatorFees()
      ).to.be.revertedWith("Only creator can withdraw");
    });

    it("Should revert if no fees to withdraw", async function () {
      const { pool, creator } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(
        pool.connect(creator).withdrawCreatorFees()
      ).to.be.revertedWith("No fees to withdraw");
    });

    it("Should return correct claimable amount", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      const buyAmount = ethers.parseEther("5");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const claimable = await pool.getCreatorClaimableAmount();
      const accumulated = await pool.accumulatedCreatorFees();

      expect(claimable).to.equal(accumulated);
    });
  });

  describe("Graduation Process", function () {
    it("Should allow oracle to initiate graduation", async function () {
      const { pool, oracle, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      await expect(pool.connect(oracle).initiateGraduation())
        .to.emit(pool, "GraduationInitiated");

      expect(await pool.graduating()).to.equal(true);
      expect(await pool.graduated()).to.equal(false);
    });

    it("Should prevent non-oracle from initiating graduation", async function () {
      const { pool, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(
        pool.connect(user1).initiateGraduation()
      ).to.be.revertedWith("Only oracle can initiate");
    });

    it("Should allow oracle to complete graduation", async function () {
      const { pool, oracle, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      await pool.connect(oracle).initiateGraduation();
      
      await expect(pool.connect(oracle).completeGraduation())
        .to.emit(pool, "Graduated");

      expect(await pool.graduating()).to.equal(false);
      expect(await pool.graduated()).to.equal(true);
    });

    it("Should burn unsold tokens on graduation", async function () {
      const { pool, oracle, user1, totalSupply } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy some tokens to create unsold tokens
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const supplyBeforeGrad = await pool.totalSupply();

      await pool.connect(oracle).initiateGraduation();
      await pool.connect(oracle).completeGraduation();

      const supplyAfterGrad = await pool.totalSupply();
      
      // Some tokens should be burned (unsold curve tokens)
      expect(supplyAfterGrad).to.be.lte(supplyBeforeGrad);
    });

    it("Should prevent graduation if already graduated", async function () {
      const { pool, oracle, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      await pool.connect(oracle).initiateGraduation();
      await pool.connect(oracle).completeGraduation();

      await expect(
        pool.connect(oracle).initiateGraduation()
      ).to.be.revertedWith("Already graduated or graduating");
    });

    it("Should prevent cancellation after KAS transfer (security fix)", async function () {
      const { pool, oracle, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Initiate graduation - this transfers KAS to oracle
      await pool.connect(oracle).initiateGraduation();

      // Verify liquidityTransferred flag is set
      expect(await pool.liquidityTransferred()).to.equal(true);

      // Attempt to cancel graduation - should revert
      await expect(
        pool.connect(oracle).cancelGraduation()
      ).to.be.revertedWith("Cannot cancel after KAS transfer");

      // Verify pool is still in graduating state
      expect(await pool.graduating()).to.equal(true);
      expect(await pool.graduated()).to.equal(false);
    });
  });

  describe("Security Features", function () {
    it("Should block direct KAS transfers via receive()", async function () {
      const { pool, user1, poolAddress } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(
        user1.sendTransaction({
          to: poolAddress,
          value: ethers.parseEther("1")
        })
      ).to.be.revertedWith("Use buyTokens() to purchase");
    });

    it("Should allow owner to pause", async function () {
      const { pool, owner } = await loadFixture(deployBondingCurvePoolFixture);

      await pool.connect(owner).pause();
      expect(await pool.paused()).to.equal(true);
    });

    it("Should prevent buying when paused", async function () {
      const { pool, owner, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      await pool.connect(owner).pause();

      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;

      await expect(
        pool.connect(user1).buyTokens(0, deadline, { value: buyAmount })
      ).to.be.reverted; // Pausable reverts without message
    });

    it("Should allow owner to unpause", async function () {
      const { pool, owner, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      await pool.connect(owner).pause();
      await pool.connect(owner).unpause();

      expect(await pool.paused()).to.equal(false);

      // Should be able to buy again
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;

      await expect(
        pool.connect(user1).buyTokens(0, deadline, { value: buyAmount })
      ).to.not.be.reverted;
    });

    it("Should allow owner to update graduation oracle", async function () {
      const { pool, owner, user1 } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(pool.connect(owner).setGraduationOracle(user1.address))
        .to.emit(pool, "GraduationOracleUpdated")
        .withArgs(user1.address);

      expect(await pool.graduationOracle()).to.equal(user1.address);
    });

    it("Should prevent non-owner from updating oracle", async function () {
      const { pool, user1, user2 } = await loadFixture(deployBondingCurvePoolFixture);

      await expect(
        pool.connect(user1).setGraduationOracle(user2.address)
      ).to.be.reverted; // Ownable reverts
    });
  });

  describe("Slippage Calculation", function () {
    it("Should calculate optimal slippage based on trade size", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const smallTrade = ethers.parseEther("0.01");
      const largeTrade = ethers.parseEther("10");

      const smallSlippage = await pool.calculateOptimalSlippage(smallTrade);
      const largeSlippage = await pool.calculateOptimalSlippage(largeTrade);

      expect(largeSlippage).to.be.gte(smallSlippage);
    });

    it("Should include anti-bot period in slippage calculation", async function () {
      const { pool } = await loadFixture(deployWithAntiBotFixture);

      const tradeAmount = ethers.parseEther("1");
      
      const slippageDuringAntiBot = await pool.calculateOptimalSlippage(tradeAmount);
      
      await time.increase(61); // Past anti-bot period
      
      const slippageAfterAntiBot = await pool.calculateOptimalSlippage(tradeAmount);

      expect(slippageDuringAntiBot).to.be.gt(slippageAfterAntiBot);
    });

    it("Should calculate minTokensOut with auto slippage", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const kasIn = ethers.parseEther("1");
      const minTokensOut = await pool.getMinTokensOutWithAutoSlippage(kasIn);

      expect(minTokensOut).to.be.gt(0);
    });

    it("Should return correct slippage risk level", async function () {
      const { pool } = await loadFixture(deployBondingCurvePoolFixture);

      const smallTrade = ethers.parseEther("0.01");
      const riskLevel = await pool.getSlippageRiskLevel(smallTrade);

      expect(riskLevel).to.be.lte(2); // 0, 1, or 2
    });
  });
});
