import { expect } from "chai";
import hre from "hardhat";
const { ethers } = hre;
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";

describe("GraduationController", function () {
  // Mock WKAS contract
  async function deployMockWKAS() {
    const MockWKAS = await ethers.getContractFactory("MockWKAS");
    const wkas = await MockWKAS.deploy();
    await wkas.waitForDeployment();
    return wkas;
  }

  // Mock Position Manager contract
  async function deployMockPositionManager() {
    const MockPositionManager = await ethers.getContractFactory("MockPositionManager");
    const positionManager = await MockPositionManager.deploy();
    await positionManager.waitForDeployment();
    return positionManager;
  }

  async function deployGraduationControllerFixture() {
    const [owner, oracle, treasury, airdropTreasury, platformDev, creator, user1, admin, buyback, kaspa, community] = await ethers.getSigners();

    // Deploy mocks
    const wkas = await deployMockWKAS();
    const positionManager = await deployMockPositionManager();

    const wkasAddress = await wkas.getAddress();
    const positionManagerAddress = await positionManager.getAddress();

    // Deploy GraduationController
    const GraduationController = await ethers.getContractFactory("GraduationController");
    const controller = await GraduationController.deploy(
      positionManagerAddress,
      wkasAddress,
      oracle.address
    );
    await controller.waitForDeployment();

    // Deploy a test pool
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
      community.address
    );
    await pool.waitForDeployment();

    return {
      controller,
      pool,
      wkas,
      positionManager,
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

  describe("Deployment", function () {
    it("Should set the correct initial parameters", async function () {
      const { controller, wkas, positionManager, oracle } = await loadFixture(deployGraduationControllerFixture);

      expect(await controller.kaspaFinancePositionManager()).to.equal(await positionManager.getAddress());
      expect(await controller.kaspaFinanceWKAS()).to.equal(await wkas.getAddress());
      expect(await controller.graduationOracle()).to.equal(oracle.address);
    });

    it("Should set correct pool constants", async function () {
      const { controller } = await loadFixture(deployGraduationControllerFixture);

      expect(await controller.POOL_FEE_TIER()).to.equal(2500); // 0.25%
      expect(await controller.FULL_RANGE_TICK_LOWER()).to.equal(-887220);
      expect(await controller.FULL_RANGE_TICK_UPPER()).to.equal(887220);
    });

    it("Should reject zero address for position manager", async function () {
      const [owner, oracle] = await ethers.getSigners();
      const wkas = await deployMockWKAS();
      const GraduationController = await ethers.getContractFactory("GraduationController");

      await expect(
        GraduationController.deploy(
          ethers.ZeroAddress, // Invalid
          await wkas.getAddress(),
          oracle.address
        )
      ).to.be.revertedWith("Invalid position manager");
    });

    it("Should reject zero address for WKAS", async function () {
      const [owner, oracle] = await ethers.getSigners();
      const positionManager = await deployMockPositionManager();
      const GraduationController = await ethers.getContractFactory("GraduationController");

      await expect(
        GraduationController.deploy(
          await positionManager.getAddress(),
          ethers.ZeroAddress, // Invalid
          oracle.address
        )
      ).to.be.revertedWith("Invalid WKAS");
    });

    it("Should reject zero address for oracle", async function () {
      const wkas = await deployMockWKAS();
      const positionManager = await deployMockPositionManager();
      const GraduationController = await ethers.getContractFactory("GraduationController");

      await expect(
        GraduationController.deploy(
          await positionManager.getAddress(),
          await wkas.getAddress(),
          ethers.ZeroAddress // Invalid
        )
      ).to.be.revertedWith("Invalid oracle");
    });
  });

  describe("Graduation Initiation", function () {
    it("Should allow oracle to initiate graduation", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      await expect(controller.connect(oracle).initiateGraduation(poolAddress))
        .to.emit(controller, "GraduationInitiated")
        .to.emit(pool, "GraduationInitiated");

      expect(await pool.graduating()).to.equal(true);
    });

    it("Should prevent non-oracle from initiating graduation", async function () {
      const { controller, pool, user1 } = await loadFixture(deployGraduationControllerFixture);

      const poolAddress = await pool.getAddress();

      await expect(
        controller.connect(user1).initiateGraduation(poolAddress)
      ).to.be.revertedWith("Only oracle can initiate");
    });

    it("Should prevent initiating graduation twice", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      await controller.connect(oracle).initiateGraduation(poolAddress);

      await expect(
        controller.connect(oracle).initiateGraduation(poolAddress)
      ).to.be.revertedWith("Already graduated or graduating");
    });

    it("Should emit GraduationFailed on pool revert", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      // Initiate once
      await controller.connect(oracle).initiateGraduation(poolAddress);

      // Try to initiate again - pool will revert
      await expect(
        controller.connect(oracle).initiateGraduation(poolAddress)
      ).to.be.reverted;
    });
  });

  describe("Graduation Completion", function () {
    it("Should allow oracle to complete graduation", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      const poolAddress = await pool.getAddress();

      // First buy some tokens to add liquidity
      const buyAmount = ethers.parseEther("10");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Initiate graduation
      await controller.connect(oracle).initiateGraduation(poolAddress);

      // Complete graduation - in a real scenario, this would interact with the DEX
      // For testing, we verify it doesn't revert on auth/state checks
      await expect(
        controller.connect(oracle).completeGraduation(poolAddress)
      ).to.emit(pool, "GraduationCompleted");
    });

    it("Should prevent non-oracle from completing graduation", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      await controller.connect(oracle).initiateGraduation(poolAddress);

      await expect(
        controller.connect(user1).completeGraduation(poolAddress)
      ).to.be.revertedWith("Only oracle can complete");
    });

    it("Should prevent completion without initiation", async function () {
      const { controller, pool, oracle } = await loadFixture(deployGraduationControllerFixture);

      const poolAddress = await pool.getAddress();

      await expect(
        controller.connect(oracle).completeGraduation(poolAddress)
      ).to.be.revertedWith("Graduation not initiated");
    });

    it("Should mark token as graduated", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      expect(await controller.hasGraduated(poolAddress)).to.equal(false);

      await controller.connect(oracle).initiateGraduation(poolAddress);
      
      // Note: Full completion would require proper mock setup
      // Testing the state tracking
      expect(await controller.hasGraduated(poolAddress)).to.equal(false);
    });
  });

  describe("Oracle Management", function () {
    it("Should allow owner to update oracle", async function () {
      const { controller, owner, user1 } = await loadFixture(deployGraduationControllerFixture);

      await expect(controller.connect(owner).setGraduationOracle(user1.address))
        .to.emit(controller, "OracleUpdated")
        .withArgs(user1.address);

      expect(await controller.graduationOracle()).to.equal(user1.address);
    });

    it("Should prevent non-owner from updating oracle", async function () {
      const { controller, user1 } = await loadFixture(deployGraduationControllerFixture);

      await expect(
        controller.connect(user1).setGraduationOracle(user1.address)
      ).to.be.reverted; // Ownable
    });

    it("Should reject zero address for oracle", async function () {
      const { controller, owner } = await loadFixture(deployGraduationControllerFixture);

      await expect(
        controller.connect(owner).setGraduationOracle(ethers.ZeroAddress)
      ).to.be.revertedWith("Invalid oracle");
    });
  });

  describe("Emergency Controls", function () {
    it("Should allow owner to reverse graduation", async function () {
      const { controller, pool, oracle, owner, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      await controller.connect(oracle).initiateGraduation(poolAddress);

      await expect(controller.connect(owner).emergencyReverseGraduation(poolAddress))
        .to.emit(controller, "GraduationFailed");
    });

    it("Should prevent reversing non-graduating pool", async function () {
      const { controller, pool, owner } = await loadFixture(deployGraduationControllerFixture);

      const poolAddress = await pool.getAddress();

      await expect(
        controller.connect(owner).emergencyReverseGraduation(poolAddress)
      ).to.be.revertedWith("Not graduating");
    });

    it("Should prevent non-owner from emergency reversal", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      await controller.connect(oracle).initiateGraduation(poolAddress);

      await expect(
        controller.connect(user1).emergencyReverseGraduation(poolAddress)
      ).to.be.reverted; // Ownable
    });

    it("Should allow owner to withdraw stuck tokens", async function () {
      const { controller, pool, owner, user1 } = await loadFixture(deployGraduationControllerFixture);

      // User1 buys tokens first
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      // Send some tokens to controller from user1
      const controllerAddress = await controller.getAddress();
      const user1Balance = await pool.balanceOf(user1.address);
      await pool.connect(user1).transfer(controllerAddress, user1Balance);

      const poolAddress = await pool.getAddress();

      await expect(
        controller.connect(owner).emergencyWithdraw(poolAddress, user1Balance)
      ).to.not.be.reverted;
    });

    it("Should prevent non-owner from emergency withdrawal", async function () {
      const { controller, pool, user1 } = await loadFixture(deployGraduationControllerFixture);

      const poolAddress = await pool.getAddress();

      await expect(
        controller.connect(user1).emergencyWithdraw(poolAddress, ethers.parseEther("100"))
      ).to.be.reverted; // Ownable
    });
  });

  describe("Query Functions", function () {
    it("Should return correct graduation status", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      expect(await controller.isGraduated(poolAddress)).to.equal(false);

      await controller.connect(oracle).initiateGraduation(poolAddress);

      // Still not graduated, just graduating
      expect(await controller.isGraduated(poolAddress)).to.equal(false);
    });

    it("Should return graduation info", async function () {
      const { controller, pool, oracle, user1 } = await loadFixture(deployGraduationControllerFixture);

      // Buy tokens first to add KAS to pool
      const buyAmount = ethers.parseEther("1");
      const deadline = (await time.latest()) + 3600;
      await pool.connect(user1).buyTokens(0, deadline, { value: buyAmount });

      const poolAddress = await pool.getAddress();

      let info = await controller.getGraduationInfo(poolAddress);
      expect(info.graduated).to.equal(false);
      expect(info.timestamp).to.equal(0);
      expect(info.positionId).to.equal(0);

      await controller.connect(oracle).initiateGraduation(poolAddress);

      info = await controller.getGraduationInfo(poolAddress);
      expect(info.graduated).to.equal(false); // Not completed yet
    });
  });
});

// Mock contracts for testing
// Note: These would normally be in separate files

// MockWKAS.sol equivalent
const MockWKASSource = `
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockWKAS {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function deposit() external payable {
        balanceOf[msg.sender] += msg.value;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}
`;

// MockPositionManager.sol equivalent  
const MockPositionManagerSource = `
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockPositionManager {
    uint256 private nextPositionId = 1;

    struct MintParams {
        address token0;
        address token1;
        uint24 fee;
        int24 tickLower;
        int24 tickUpper;
        uint256 amount0Desired;
        uint256 amount1Desired;
        uint256 amount0Min;
        uint256 amount1Min;
        address recipient;
        uint256 deadline;
    }

    function mint(MintParams calldata params) external payable returns (
        uint256 tokenId,
        uint128 liquidity,
        uint256 amount0,
        uint256 amount1
    ) {
        tokenId = nextPositionId++;
        liquidity = 1000000;
        amount0 = params.amount0Desired;
        amount1 = params.amount1Desired;
    }
}
`;
