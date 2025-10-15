import { expect } from "chai";
import hre from "hardhat";
const { ethers } = hre;
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";

describe("TokenFactory", function () {
  // Deployment fixture
  async function deployTokenFactoryFixture() {
    const [owner, graduationController, treasury, airdropTreasury, platformDev, user1, user2, oracle, admin, buyback, kaspa, community] = await ethers.getSigners();

    const VestingManager = await ethers.getContractFactory("VestingManager");
    const vestingManager = await VestingManager.deploy();
    await vestingManager.waitForDeployment();
    const vestingManagerAddress = await vestingManager.getAddress();

    const TokenFactory = await ethers.getContractFactory("TokenFactory");
    
    const factory = await TokenFactory.deploy(
      graduationController.address,
      treasury.address,
      airdropTreasury.address,
      platformDev.address,
      oracle.address,
      admin.address,
      buyback.address,
      kaspa.address,
      community.address,
      vestingManagerAddress
    );
    
    await factory.waitForDeployment();
    const factoryAddress = await factory.getAddress();

    return { 
      factory,
      factoryAddress,
      vestingManager,
      vestingManagerAddress,
      owner,
      graduationController,
      treasury,
      airdropTreasury,
      platformDev,
      user1,
      user2
    };
  }

  describe("Deployment", function () {
    it("Should set the correct initial parameters", async function () {
      const { factory, graduationController, treasury, airdropTreasury, platformDev } = await loadFixture(deployTokenFactoryFixture);

      expect(await factory.graduationController()).to.equal(graduationController.address);
      expect(await factory.treasury()).to.equal(treasury.address);
      expect(await factory.airdropTreasury()).to.equal(airdropTreasury.address);
      expect(await factory.platformDevelopmentWallet()).to.equal(platformDev.address);
      expect(await factory.deploymentCooldown()).to.equal(60);
    });

    it("Should reject invalid constructor parameters", async function () {
      const [owner, graduationController, treasury, airdropTreasury, platformDev, oracle, admin, buyback, kaspa, community] = await ethers.getSigners();
      const TokenFactory = await ethers.getContractFactory("TokenFactory");
      const VestingManager = await ethers.getContractFactory("VestingManager");
      const vestingManager = await VestingManager.deploy();
      await vestingManager.waitForDeployment();
      const vestingManagerAddress = await vestingManager.getAddress();

      await expect(
        TokenFactory.deploy(
          ethers.ZeroAddress, // Invalid graduation controller
          treasury.address,
          airdropTreasury.address,
          platformDev.address,
          oracle.address,
          admin.address,
          buyback.address,
          kaspa.address,
          community.address,
          vestingManagerAddress
        )
      ).to.be.revertedWith("Bad controller");

      await expect(
        TokenFactory.deploy(
          graduationController.address,
          ethers.ZeroAddress, // Invalid treasury
          airdropTreasury.address,
          platformDev.address,
          oracle.address,
          admin.address,
          buyback.address,
          kaspa.address,
          community.address,
          vestingManagerAddress
        )
      ).to.be.revertedWith("Bad treasury");
    });
  });

  describe("Token Creation", function () {
    it("Should create a token with valid parameters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const tx = await factory.connect(user1).createToken(
        "Test Token",
        "TEST",
        ethers.parseEther("1000000"), // 1M tokens
        "A test token",
        "https://example.com/image.png",
        "https://twitter.com/test",
        "https://t.me/test",
        "https://test.com",
        false,
        0, 0, 0, 0  // BASIC token (no vesting)
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log => {
        try {
          return factory.interface.parseLog(log).name === "TokenCreated";
        } catch {
          return false;
        }
      });

      expect(event).to.not.be.undefined;

      const tokenCount = await factory.getDeployedTokenCount();
      expect(tokenCount).to.equal(1);
    });

    it("Should store token metadata correctly", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const tokenParams = {
        name: "Test Token",
        symbol: "TEST",
        totalSupply: ethers.parseEther("1000000"),
        description: "A test token",
        imageUrl: "https://example.com/image.png",
        twitterUrl: "https://twitter.com/test",
        telegramUrl: "https://t.me/test",
        websiteUrl: "https://test.com",
        antiBotEnabled: true
      };

      const tx = await factory.connect(user1).createToken(
        tokenParams.name,
        tokenParams.symbol,
        tokenParams.totalSupply,
        tokenParams.description,
        tokenParams.imageUrl,
        tokenParams.twitterUrl,
        tokenParams.telegramUrl,
        tokenParams.websiteUrl,
        tokenParams.antiBotEnabled,
        0, 0, 0, 0  // BASIC token (no vesting)
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log => {
        try {
          return factory.interface.parseLog(log).name === "TokenCreated";
        } catch {
          return false;
        }
      });

      const parsedEvent = factory.interface.parseLog(event);
      const tokenAddress = parsedEvent.args[0];

      const tokenInfo = await factory.getTokenInfo(tokenAddress);
      
      expect(tokenInfo.name).to.equal(tokenParams.name);
      expect(tokenInfo.symbol).to.equal(tokenParams.symbol);
      expect(tokenInfo.totalSupply).to.equal(tokenParams.totalSupply);
      expect(tokenInfo.description).to.equal(tokenParams.description);
      expect(tokenInfo.imageUrl).to.equal(tokenParams.imageUrl);
      expect(tokenInfo.twitterUrl).to.equal(tokenParams.twitterUrl);
      expect(tokenInfo.telegramUrl).to.equal(tokenParams.telegramUrl);
      expect(tokenInfo.websiteUrl).to.equal(tokenParams.websiteUrl);
      expect(tokenInfo.antiBotEnabled).to.equal(tokenParams.antiBotEnabled);
      expect(tokenInfo.creator).to.equal(user1.address);
    });

    it("Should emit TokenCreated event with correct parameters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          ethers.parseEther("1000000"),
          "A test token",
          "https://example.com/image.png",
          "https://twitter.com/test",
          "https://t.me/test",
          "https://test.com",
          true,
          0, 0, 0, 0  // BASIC token (no vesting)
        )
      ).to.emit(factory, "TokenCreated");
    });

    it("Should add token to deployedTokens array", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const tx = await factory.connect(user1).createToken(
        "Test Token",
        "TEST",
        ethers.parseEther("1000000"),
        "A test token",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0  // BASIC token (no vesting)
      );

      const tokens = await factory.getDeployedTokens(0, 10);
      expect(tokens.length).to.equal(1);
    });
  });

  describe("Input Validation", function () {
    it("Should reject empty token name", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).createToken(
          "", // Empty name
          "TEST",
          ethers.parseEther("1000000"),
          "Description",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Bad name");
    });

    it("Should reject name longer than 32 characters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const longName = "A".repeat(33);

      await expect(
        factory.connect(user1).createToken(
          longName,
          "TEST",
          ethers.parseEther("1000000"),
          "Description",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Bad name");
    });

    it("Should reject empty symbol", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "", // Empty symbol
          ethers.parseEther("1000000"),
          "Description",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Bad symbol");
    });

    it("Should reject symbol longer than 10 characters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const longSymbol = "A".repeat(11);

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          longSymbol,
          ethers.parseEther("1000000"),
          "Description",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Bad symbol");
    });

    it("Should reject total supply below minimum (1M)", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const tooLow = ethers.parseEther("999999"); // Below 1M

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          tooLow,
          "Description",
          "",
          "",
          "",
          "",
          false, 0, 0, 0, 0
        )
      ).to.be.revertedWith("Supply low");
    });

    it("Should reject total supply above maximum (1B)", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const tooHigh = ethers.parseEther("1000000001"); // Above 1B

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          tooHigh,
          "Description",
          "",
          "",
          "",
          "",
          false, 0, 0, 0, 0
        )
      ).to.be.revertedWith("Supply high");
    });

    it("Should reject description longer than 280 characters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const longDescription = "A".repeat(281);

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          ethers.parseEther("1000000"),
          longDescription,
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Desc long");
    });

    it("Should accept description of exactly 280 characters", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      const maxDescription = "A".repeat(280);

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          ethers.parseEther("1000000"),
          maxDescription,
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.not.be.reverted;
    });
  });

  describe("Anti-Spam Cooldown", function () {
    it("Should enforce 60 second deployment cooldown", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      // First deployment should succeed
      await factory.connect(user1).createToken(
        "First Token",
        "FIRST",
        ethers.parseEther("1000000"),
        "First token",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      // Immediate second deployment should fail
      await expect(
        factory.connect(user1).createToken(
          "Second Token",
          "SECOND",
          ethers.parseEther("1000000"),
          "Second token",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.revertedWith("Wait");
    });

    it("Should allow deployment after cooldown expires", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await factory.connect(user1).createToken(
        "First Token",
        "FIRST",
        ethers.parseEther("1000000"),
        "First token",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      // Wait for cooldown to expire
      await time.increase(60);

      // Should succeed now
      await expect(
        factory.connect(user1).createToken(
          "Second Token",
          "SECOND",
          ethers.parseEther("1000000"),
          "Second token",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.not.be.reverted;
    });

    it("Should track cooldown per user independently", async function () {
      const { factory, user1, user2 } = await loadFixture(deployTokenFactoryFixture);

      // User1 creates a token
      await factory.connect(user1).createToken(
        "User1 Token",
        "U1",
        ethers.parseEther("1000000"),
        "User1's token",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      // User2 should still be able to create immediately
      await expect(
        factory.connect(user2).createToken(
          "User2 Token",
          "U2",
          ethers.parseEther("1000000"),
          "User2's token",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.not.be.reverted;
    });

    it("Should correctly report canDeploy status", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      expect(await factory.canDeploy(user1.address)).to.equal(true);

      await factory.connect(user1).createToken(
        "Test Token",
        "TEST",
        ethers.parseEther("1000000"),
        "Test",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      expect(await factory.canDeploy(user1.address)).to.equal(false);

      await time.increase(60);

      expect(await factory.canDeploy(user1.address)).to.equal(true);
    });

    // Test removed: getSecondsUntilNextDeployment function was removed during VestingManager refactoring
  });

  describe("Pause/Unpause Functionality", function () {
    it("Should allow owner to pause", async function () {
      const { factory, owner } = await loadFixture(deployTokenFactoryFixture);

      await factory.connect(owner).pause();
      expect(await factory.paused()).to.equal(true);
    });

    it("Should prevent token creation when paused", async function () {
      const { factory, owner, user1 } = await loadFixture(deployTokenFactoryFixture);

      await factory.connect(owner).pause();

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          ethers.parseEther("1000000"),
          "Test",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.be.reverted;
    });

    it("Should allow owner to unpause", async function () {
      const { factory, owner } = await loadFixture(deployTokenFactoryFixture);

      await factory.connect(owner).pause();
      await factory.connect(owner).unpause();
      
      expect(await factory.paused()).to.equal(false);
    });

    it("Should allow token creation after unpause", async function () {
      const { factory, owner, user1 } = await loadFixture(deployTokenFactoryFixture);

      await factory.connect(owner).pause();
      await factory.connect(owner).unpause();

      await expect(
        factory.connect(user1).createToken(
          "Test Token",
          "TEST",
          ethers.parseEther("1000000"),
          "Test",
          "",
          "",
          "",
          "",
          false,
          0, 0, 0, 0
        )
      ).to.not.be.reverted;
    });

    it("Should prevent non-owner from pausing", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).pause()
      ).to.be.reverted; // Ownable
    });
  });

  describe("Admin Functions", function () {
    it("Should allow owner to update deployment cooldown", async function () {
      const { factory, owner } = await loadFixture(deployTokenFactoryFixture);

      const newCooldown = 120;

      await expect(factory.connect(owner).setDeploymentCooldown(newCooldown))
        .to.emit(factory, "DeploymentCooldownUpdated")
        .withArgs(newCooldown);

      expect(await factory.deploymentCooldown()).to.equal(newCooldown);
    });

    it("Should reject cooldown longer than 1 hour", async function () {
      const { factory, owner } = await loadFixture(deployTokenFactoryFixture);

      const tooLong = 3601; // > 1 hour

      await expect(
        factory.connect(owner).setDeploymentCooldown(tooLong)
      ).to.be.revertedWith("CD long");
    });

    it("Should allow owner to update graduation controller", async function () {
      const { factory, owner, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(factory.connect(owner).setGraduationController(user1.address))
        .to.emit(factory, "GraduationControllerUpdated")
        .withArgs(user1.address);

      expect(await factory.graduationController()).to.equal(user1.address);
    });

    it("Should reject zero address for graduation controller", async function () {
      const { factory, owner } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(owner).setGraduationController(ethers.ZeroAddress)
      ).to.be.revertedWith("Bad ctrl");
    });

    it("Should prevent non-owner from updating cooldown", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).setDeploymentCooldown(120)
      ).to.be.reverted; // Ownable
    });

    it("Should prevent non-owner from updating graduation controller", async function () {
      const { factory, user1, user2 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).setGraduationController(user2.address)
      ).to.be.reverted; // Ownable
    });
  });

  // Emergency Functions tests removed: emergencyWithdrawToken and emergencyWithdrawKAS functions were removed during VestingManager refactoring

  describe("Query Functions", function () {
    it("Should return correct deployed token count", async function () {
      const { factory, user1, user2 } = await loadFixture(deployTokenFactoryFixture);

      expect(await factory.getDeployedTokenCount()).to.equal(0);

      await factory.connect(user1).createToken(
        "Token 1",
        "TK1",
        ethers.parseEther("1000000"),
        "First",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      expect(await factory.getDeployedTokenCount()).to.equal(1);

      await time.increase(60);

      await factory.connect(user2).createToken(
        "Token 2",
        "TK2",
        ethers.parseEther("1000000"),
        "Second",
        "",
        "",
        "",
        "",
        false,
        0, 0, 0, 0
      );

      expect(await factory.getDeployedTokenCount()).to.equal(2);
    });

    it("Should return paginated deployed tokens", async function () {
      const { factory, user1, user2 } = await loadFixture(deployTokenFactoryFixture);

      // Create 3 tokens
      await factory.connect(user1).createToken("Token 1", "TK1", ethers.parseEther("1000000"), "1", "", "", "", "", false, 0, 0, 0, 0);
      
      await time.increase(60);
      await factory.connect(user2).createToken("Token 2", "TK2", ethers.parseEther("1000000"), "2", "", "", "", "", false, 0, 0, 0, 0);
      
      await time.increase(60);
      await factory.connect(user1).createToken("Token 3", "TK3", ethers.parseEther("1000000"), "3", "", "", "", "", false, 0, 0, 0, 0);

      const tokens = await factory.getDeployedTokens(0, 2);
      expect(tokens.length).to.equal(2);

      const allTokens = await factory.getDeployedTokens(0, 10);
      expect(allTokens.length).to.equal(3);
    });

    it("Should revert on invalid offset", async function () {
      const { factory } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.getDeployedTokens(10, 5)
      ).to.be.revertedWith("Bad offset");
    });
  });

  describe("VestingManager Integration", function () {
    it("Should deploy PRO token with vesting contracts via VestingManager", async function () {
      const { factory, user1, airdropTreasury } = await loadFixture(deployTokenFactoryFixture);

      const tx = await factory.connect(user1).createToken(
        "PRO Token",
        "PRO",
        ethers.parseEther("1000000"),
        "PRO token with vesting",
        "",
        "",
        "",
        "",
        false,
        10,  // 10% vesting
        30,  // 30% airdrops
        40,  // 40% marketing
        30   // 30% team
      );

      const receipt = await tx.wait();
      const vestingEvent = receipt.logs.find(log => {
        try {
          return factory.interface.parseLog(log).name === "VestingDeployed";
        } catch {
          return false;
        }
      });

      expect(vestingEvent).to.not.be.undefined;
      const parsed = factory.interface.parseLog(vestingEvent);
      expect(parsed.args.airdropAllocation).to.equal(30);
      expect(parsed.args.marketingAllocation).to.equal(40);
      expect(parsed.args.teamAllocation).to.equal(30);
    });

    it("Should reject vesting allocations that don't sum to 100%", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).createToken(
          "PRO Token",
          "PRO",
          ethers.parseEther("1000000"),
          "Invalid vesting",
          "",
          "",
          "",
          "",
          false,
          10,  // 10% vesting
          30,  // 30% airdrops
          30,  // 30% marketing
          30   // 30% team (total = 90%, should fail)
        )
      ).to.be.revertedWith("Allocations must sum to 100%");
    });

    it("Should reject vesting percentage over 25%", async function () {
      const { factory, user1 } = await loadFixture(deployTokenFactoryFixture);

      await expect(
        factory.connect(user1).createToken(
          "PRO Token",
          "PRO",
          ethers.parseEther("1000000"),
          "Too much vesting",
          "",
          "",
          "",
          "",
          false,
          26,  // 26% vesting (over limit)
          50,  // 50% airdrops
          25,  // 25% marketing
          25   // 25% team
        )
      ).to.be.revertedWith("Vesting exceeds 25%");
    });

    // Test removed: With current constraints (min 1M supply, min 1% vesting, uint8 allocations), 
    // it's not possible to trigger "allocation too small" error since 1M * 1% * 1% = 100 tokens (exactly at minimum)
  });
});
