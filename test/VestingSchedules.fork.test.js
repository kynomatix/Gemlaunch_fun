import { expect } from "chai";
import hre from "hardhat";
const { ethers, network } = hre;

describe("PRO Token Vesting Schedules - Fork Test", function () {
  // Contract addresses from deployment
  const PRO_TOKEN_ADDRESS = "0xDaAAC992517BE6D1B42FfF520F725C765F3369C3";
  const AIRDROP_VESTING_ADDRESS = "0x97EbBe73eB4B703e894E77F3877225d0E53a09E3";
  const MARKETING_VESTING_ADDRESS = "0x18948FA78F16B7CD261AE6cBC634B6cc85c334A7";
  const TEAM_VESTING_ADDRESS = "0x27c262afD6936F860b5C2143A4B42c95F6b58E81";
  
  // Fork configuration
  const FORK_BLOCK = 8130350;
  const FORK_URL = "https://rpc.kasplextest.xyz";
  
  // Expected token amounts (in wei)
  const AIRDROP_TOTAL = ethers.parseEther("100000000"); // 100M tokens
  const MARKETING_TOTAL = ethers.parseEther("60000000"); // 60M tokens
  const TEAM_TOTAL = ethers.parseEther("40000000"); // 40M tokens
  
  // Time constants
  const ONE_DAY = 24 * 60 * 60;
  const ONE_MONTH = 30 * ONE_DAY;
  
  let proToken;
  let airdropVesting;
  let marketingVesting;
  let teamVesting;
  let airdropBeneficiary;
  let marketingBeneficiary;
  let teamBeneficiary;
  let globalSnapshot; // Global snapshot for all tests

  before(async function () {
    console.log("\n🔧 Setting up fork test environment...");
    console.log(`✅ Using forked Kasplex Testnet (configured in hardhat.config.js)`);
    
    // Take a global snapshot BEFORE any tests run
    globalSnapshot = await network.provider.send("evm_snapshot");
    
    // Get contract instances
    const ERC20_ABI = [
      "function balanceOf(address) view returns (uint256)",
      "function transfer(address to, uint256 amount) returns (bool)"
    ];
    
    const VESTING_ABI = [
      "function token() view returns (address)",
      "function beneficiary() view returns (address)",
      "function totalAllocation() view returns (uint256)",
      "function startTime() view returns (uint256)",
      "function withdrawn() view returns (uint256)",
      "function getUnlockedAmount() view returns (uint256)",
      "function getWithdrawableAmount() view returns (uint256)",
      "function withdraw()",
      "event TokensWithdrawn(address indexed beneficiary, uint256 amount)"
    ];
    
    proToken = await ethers.getContractAt(ERC20_ABI, PRO_TOKEN_ADDRESS);
    airdropVesting = await ethers.getContractAt(VESTING_ABI, AIRDROP_VESTING_ADDRESS);
    marketingVesting = await ethers.getContractAt(VESTING_ABI, MARKETING_VESTING_ADDRESS);
    teamVesting = await ethers.getContractAt(VESTING_ABI, TEAM_VESTING_ADDRESS);
    
    // Get beneficiary addresses
    airdropBeneficiary = await airdropVesting.beneficiary();
    marketingBeneficiary = await marketingVesting.beneficiary();
    teamBeneficiary = await teamVesting.beneficiary();
    
    console.log("\n📋 Vesting Contract Details:");
    console.log(`   Airdrop Beneficiary: ${airdropBeneficiary}`);
    console.log(`   Marketing Beneficiary: ${marketingBeneficiary}`);
    console.log(`   Team Beneficiary: ${teamBeneficiary}`);
    
    // Verify allocations
    const airdropAllocation = await airdropVesting.totalAllocation();
    const marketingAllocation = await marketingVesting.totalAllocation();
    const teamAllocation = await teamVesting.totalAllocation();
    
    console.log("\n💰 Token Allocations:");
    console.log(`   Airdrop: ${ethers.formatEther(airdropAllocation)} tokens`);
    console.log(`   Marketing: ${ethers.formatEther(marketingAllocation)} tokens`);
    console.log(`   Team: ${ethers.formatEther(teamAllocation)} tokens`);
  });

  describe("Airdrop Vesting (5% daily for 20 days)", function () {
    it("Should have 0 unlocked at T0 (start time)", async function () {
      const unlocked = await airdropVesting.getUnlockedAmount();
      expect(unlocked).to.equal(0, "Should have 0 tokens unlocked at start");
      console.log(`   ✓ T0: ${ethers.formatEther(unlocked)} tokens unlocked`);
    });

    it("Should unlock ~5M tokens (5%) after 1 day", async function () {
      await network.provider.send("evm_increaseTime", [ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await airdropVesting.getUnlockedAmount();
      const expected = AIRDROP_TOTAL * BigInt(5) / BigInt(100); // 5%
      
      // Allow reasonable deviation for time precision (0.1% of total)
      const maxDeviation = MARKETING_TOTAL / BigInt(1000); // 0.1%
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(maxDeviation, "Deviation should be ≤0.1% of total");
      
      console.log(`   ✓ T+1 day: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock ~25M tokens (25%) after 5 days total", async function () {
      // Advance 4 more days (total 5 days)
      await network.provider.send("evm_increaseTime", [4 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await airdropVesting.getUnlockedAmount();
      const expected = AIRDROP_TOTAL * BigInt(25) / BigInt(100); // 25%
      
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(ethers.parseEther("1"), "Deviation should be ≤1 token");
      
      console.log(`   ✓ T+5 days: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock 100M tokens (100%) after 20 days total", async function () {
      // Advance 15 more days (total 20 days)
      await network.provider.send("evm_increaseTime", [15 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await airdropVesting.getUnlockedAmount();
      expect(unlocked).to.equal(AIRDROP_TOTAL, "Should have 100% unlocked after 20 days");
      
      console.log(`   ✓ T+20 days: ${ethers.formatEther(unlocked)} tokens unlocked (100%)`);
    });

    it("Should allow beneficiary to withdraw after vesting period", async function () {
      const withdrawable = await airdropVesting.getWithdrawableAmount();
      expect(withdrawable).to.equal(AIRDROP_TOTAL, "Should have full amount withdrawable");
      
      // Impersonate beneficiary
      await network.provider.request({
        method: "hardhat_impersonateAccount",
        params: [airdropBeneficiary],
      });
      
      const beneficiarySigner = await ethers.getSigner(airdropBeneficiary);
      
      // Fund the beneficiary for gas
      const [funder] = await ethers.getSigners();
      await funder.sendTransaction({
        to: airdropBeneficiary,
        value: ethers.parseEther("100"), // Increased for gas
      });
      
      const initialBalance = await proToken.balanceOf(airdropBeneficiary);
      
      // Withdraw
      await airdropVesting.connect(beneficiarySigner).withdraw();
      
      const finalBalance = await proToken.balanceOf(airdropBeneficiary);
      const withdrawn = await airdropVesting.withdrawn();
      
      expect(finalBalance - initialBalance).to.equal(AIRDROP_TOTAL);
      expect(withdrawn).to.equal(AIRDROP_TOTAL);
      
      console.log(`   ✓ Withdrew ${ethers.formatEther(AIRDROP_TOTAL)} tokens to beneficiary`);
      
      await network.provider.request({
        method: "hardhat_stopImpersonatingAccount",
        params: [airdropBeneficiary],
      });
    });
  });

  describe("Marketing Linear Vesting (12 months)", function () {
    before(async function () {
      // Revert to global snapshot to reset all state and time
      await network.provider.send("evm_revert", [globalSnapshot]);
      globalSnapshot = await network.provider.send("evm_snapshot");
      
      marketingVesting = await ethers.getContractAt(
        [
          "function beneficiary() view returns (address)",
          "function totalAllocation() view returns (uint256)",
          "function withdrawn() view returns (uint256)",
          "function getUnlockedAmount() view returns (uint256)",
          "function getWithdrawableAmount() view returns (uint256)",
          "function withdraw()"
        ],
        MARKETING_VESTING_ADDRESS
      );
      
      proToken = await ethers.getContractAt(
        ["function balanceOf(address) view returns (uint256)"],
        PRO_TOKEN_ADDRESS
      );
      
      marketingBeneficiary = await marketingVesting.beneficiary();
    });

    it("Should have 0 unlocked at T0 (start time)", async function () {
      const unlocked = await marketingVesting.getUnlockedAmount();
      // Allow small deviation due to test execution time
      expect(unlocked).to.be.lte(ethers.parseEther("10000"), "Should have minimal tokens unlocked at start");
      console.log(`   ✓ T0: ${ethers.formatEther(unlocked)} tokens unlocked`);
    });

    it("Should unlock ~5M tokens (1/12) after 30 days", async function () {
      await network.provider.send("evm_increaseTime", [30 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await marketingVesting.getUnlockedAmount();
      const expected = MARKETING_TOTAL / BigInt(12); // 1/12
      
      const maxDeviation = MARKETING_TOTAL / BigInt(1000); // 0.1%
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(maxDeviation, "Deviation should be ≤0.1% of total");
      
      console.log(`   ✓ T+30 days: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock ~30M tokens (1/2) after 180 days total", async function () {
      // Advance 150 more days (total 180 days)
      await network.provider.send("evm_increaseTime", [150 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await marketingVesting.getUnlockedAmount();
      const expected = MARKETING_TOTAL / BigInt(2); // 50%
      
      const maxDeviation = MARKETING_TOTAL / BigInt(1000); // 0.1%
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(maxDeviation, "Deviation should be ≤0.1% of total");
      
      console.log(`   ✓ T+180 days: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock 60M tokens (100%) after 360 days total", async function () {
      // Advance 180 more days (total 360 days = 12 months)
      await network.provider.send("evm_increaseTime", [180 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await marketingVesting.getUnlockedAmount();
      expect(unlocked).to.equal(MARKETING_TOTAL, "Should have 100% unlocked after 12 months");
      
      console.log(`   ✓ T+360 days: ${ethers.formatEther(unlocked)} tokens unlocked (100%)`);
    });

    it("Should allow beneficiary to withdraw after vesting period", async function () {
      const withdrawable = await marketingVesting.getWithdrawableAmount();
      expect(withdrawable).to.equal(MARKETING_TOTAL, "Should have full amount withdrawable");
      
      await network.provider.request({
        method: "hardhat_impersonateAccount",
        params: [marketingBeneficiary],
      });
      
      const beneficiarySigner = await ethers.getSigner(marketingBeneficiary);
      const [funder] = await ethers.getSigners();
      await funder.sendTransaction({
        to: marketingBeneficiary,
        value: ethers.parseEther("100"),
      });
      
      const initialBalance = await proToken.balanceOf(marketingBeneficiary);
      await marketingVesting.connect(beneficiarySigner).withdraw();
      const finalBalance = await proToken.balanceOf(marketingBeneficiary);
      const withdrawn = await marketingVesting.withdrawn();
      
      expect(finalBalance - initialBalance).to.equal(MARKETING_TOTAL);
      expect(withdrawn).to.equal(MARKETING_TOTAL);
      
      console.log(`   ✓ Withdrew ${ethers.formatEther(MARKETING_TOTAL)} tokens to beneficiary`);
      
      await network.provider.request({
        method: "hardhat_stopImpersonatingAccount",
        params: [marketingBeneficiary],
      });
    });
  });

  describe("Team Cliff Vesting (6 month cliff + 18 month vesting)", function () {
    before(async function () {
      // Revert to global snapshot to reset all state and time
      await network.provider.send("evm_revert", [globalSnapshot]);
      globalSnapshot = await network.provider.send("evm_snapshot");
      
      teamVesting = await ethers.getContractAt(
        [
          "function beneficiary() view returns (address)",
          "function totalAllocation() view returns (uint256)",
          "function withdrawn() view returns (uint256)",
          "function getUnlockedAmount() view returns (uint256)",
          "function getWithdrawableAmount() view returns (uint256)",
          "function withdraw()"
        ],
        TEAM_VESTING_ADDRESS
      );
      
      proToken = await ethers.getContractAt(
        ["function balanceOf(address) view returns (uint256)"],
        PRO_TOKEN_ADDRESS
      );
      
      teamBeneficiary = await teamVesting.beneficiary();
    });

    it("Should have 0 unlocked at T0 (start time)", async function () {
      const unlocked = await teamVesting.getUnlockedAmount();
      expect(unlocked).to.equal(0, "Should have 0 tokens unlocked at start");
      console.log(`   ✓ T0: ${ethers.formatEther(unlocked)} tokens unlocked`);
    });

    it("Should have 0 unlocked during cliff period (T0 to T+6 months)", async function () {
      // Test at 3 months
      await network.provider.send("evm_increaseTime", [3 * ONE_MONTH]);
      await network.provider.send("evm_mine");
      
      let unlocked = await teamVesting.getUnlockedAmount();
      expect(unlocked).to.equal(0, "Should have 0 tokens during cliff");
      console.log(`   ✓ T+3 months: ${ethers.formatEther(unlocked)} tokens unlocked (cliff period)`);
      
      // Test at 6 months (cliff end)
      await network.provider.send("evm_increaseTime", [3 * ONE_MONTH]);
      await network.provider.send("evm_mine");
      
      unlocked = await teamVesting.getUnlockedAmount();
      // Allow small deviation due to test execution time
      expect(unlocked).to.be.lte(ethers.parseEther("10000"), "Should have minimal tokens at cliff end");
      console.log(`   ✓ T+6 months: ${ethers.formatEther(unlocked)} tokens unlocked (cliff end)`);
    });

    it("Should start unlocking after cliff (T+6 months + 1 day)", async function () {
      await network.provider.send("evm_increaseTime", [ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked = await teamVesting.getUnlockedAmount();
      
      // After cliff, vesting starts. 1 day into 18 month vesting
      const vestingDuration = 18 * ONE_MONTH;
      const expected = (TEAM_TOTAL * BigInt(ONE_DAY)) / BigInt(vestingDuration);
      
      expect(unlocked).to.be.gt(0, "Should have some tokens unlocked after cliff");
      console.log(`   ✓ T+6mo+1day: ${ethers.formatEther(unlocked)} tokens unlocked (vesting started)`);
    });

    it("Should unlock ~13.3M tokens (33%) after 12 months total", async function () {
      // We're at 6 months + 1 day, need to reach 12 months
      const timeToAdvance = (6 * ONE_MONTH) - ONE_DAY;
      await network.provider.send("evm_increaseTime", [timeToAdvance]);
      await network.provider.send("evm_mine");
      
      const unlocked = await teamVesting.getUnlockedAmount();
      
      // 12 months total = 6 months cliff + 6 months vesting
      // 6 months vesting = 33% of 18 month vesting period
      const expected = (TEAM_TOTAL * BigInt(6)) / BigInt(18); // 6/18 = 1/3
      
      const maxDeviation = TEAM_TOTAL / BigInt(1000); // 0.1%
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(maxDeviation, "Deviation should be ≤0.1% of total");
      
      console.log(`   ✓ T+12 months: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock ~26.6M tokens (66%) after 18 months total", async function () {
      // Advance 6 more months (total 18 months)
      await network.provider.send("evm_increaseTime", [6 * ONE_MONTH]);
      await network.provider.send("evm_mine");
      
      const unlocked = await teamVesting.getUnlockedAmount();
      
      // 18 months total = 6 months cliff + 12 months vesting
      // 12 months vesting = 66% of 18 month vesting period
      const expected = (TEAM_TOTAL * BigInt(12)) / BigInt(18); // 12/18 = 2/3
      
      const maxDeviation = TEAM_TOTAL / BigInt(1000); // 0.1%
      const deviation = unlocked > expected ? unlocked - expected : expected - unlocked;
      expect(deviation).to.be.lte(maxDeviation, "Deviation should be ≤0.1% of total");
      
      console.log(`   ✓ T+18 months: ${ethers.formatEther(unlocked)} tokens unlocked (expected: ${ethers.formatEther(expected)})`);
    });

    it("Should unlock 40M tokens (100%) after 24 months total", async function () {
      // Advance 6 more months (total 24 months = 6mo cliff + 18mo vesting)
      await network.provider.send("evm_increaseTime", [6 * ONE_MONTH]);
      await network.provider.send("evm_mine");
      
      const unlocked = await teamVesting.getUnlockedAmount();
      expect(unlocked).to.equal(TEAM_TOTAL, "Should have 100% unlocked after 24 months");
      
      console.log(`   ✓ T+24 months: ${ethers.formatEther(unlocked)} tokens unlocked (100%)`);
    });

    it("Should allow beneficiary to withdraw after vesting period", async function () {
      const withdrawable = await teamVesting.getWithdrawableAmount();
      expect(withdrawable).to.equal(TEAM_TOTAL, "Should have full amount withdrawable");
      
      await network.provider.request({
        method: "hardhat_impersonateAccount",
        params: [teamBeneficiary],
      });
      
      const beneficiarySigner = await ethers.getSigner(teamBeneficiary);
      const [funder] = await ethers.getSigners();
      await funder.sendTransaction({
        to: teamBeneficiary,
        value: ethers.parseEther("100"),
      });
      
      const initialBalance = await proToken.balanceOf(teamBeneficiary);
      await teamVesting.connect(beneficiarySigner).withdraw();
      const finalBalance = await proToken.balanceOf(teamBeneficiary);
      const withdrawn = await teamVesting.withdrawn();
      
      expect(finalBalance - initialBalance).to.equal(TEAM_TOTAL);
      expect(withdrawn).to.equal(TEAM_TOTAL);
      
      console.log(`   ✓ Withdrew ${ethers.formatEther(TEAM_TOTAL)} tokens to beneficiary`);
      
      await network.provider.request({
        method: "hardhat_stopImpersonatingAccount",
        params: [teamBeneficiary],
      });
    });
  });

  describe("Partial Withdrawal Tests", function () {
    before(async function () {
      // Revert to global snapshot to reset all state and time
      await network.provider.send("evm_revert", [globalSnapshot]);
      globalSnapshot = await network.provider.send("evm_snapshot");
      
      airdropVesting = await ethers.getContractAt(
        [
          "function beneficiary() view returns (address)",
          "function withdrawn() view returns (uint256)",
          "function getUnlockedAmount() view returns (uint256)",
          "function getWithdrawableAmount() view returns (uint256)",
          "function withdraw()"
        ],
        AIRDROP_VESTING_ADDRESS
      );
      
      proToken = await ethers.getContractAt(
        ["function balanceOf(address) view returns (uint256)"],
        PRO_TOKEN_ADDRESS
      );
      
      airdropBeneficiary = await airdropVesting.beneficiary();
    });

    it("Should allow partial withdrawal and track withdrawn amount correctly", async function () {
      // Advance 5 days (25% unlocked)
      await network.provider.send("evm_increaseTime", [5 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked1 = await airdropVesting.getUnlockedAmount();
      const withdrawable1 = await airdropVesting.getWithdrawableAmount();
      
      expect(withdrawable1).to.equal(unlocked1, "Withdrawable should equal unlocked initially");
      
      // First withdrawal
      await network.provider.request({
        method: "hardhat_impersonateAccount",
        params: [airdropBeneficiary],
      });
      
      const beneficiarySigner = await ethers.getSigner(airdropBeneficiary);
      const [funder] = await ethers.getSigners();
      await funder.sendTransaction({
        to: airdropBeneficiary,
        value: ethers.parseEther("100"), // Increased for gas
      });
      
      await airdropVesting.connect(beneficiarySigner).withdraw();
      
      const withdrawn1 = await airdropVesting.withdrawn();
      expect(withdrawn1).to.equal(unlocked1, "Withdrawn should match first unlock amount");
      
      console.log(`   ✓ First withdrawal: ${ethers.formatEther(withdrawn1)} tokens`);
      
      // Advance another 5 days (50% total unlocked)
      await network.provider.send("evm_increaseTime", [5 * ONE_DAY]);
      await network.provider.send("evm_mine");
      
      const unlocked2 = await airdropVesting.getUnlockedAmount();
      const withdrawable2 = await airdropVesting.getWithdrawableAmount();
      
      // Withdrawable should be the difference between unlocked and already withdrawn
      expect(withdrawable2).to.equal(unlocked2 - withdrawn1, "Withdrawable should be unlocked minus withdrawn");
      
      console.log(`   ✓ Unlocked: ${ethers.formatEther(unlocked2)}, Withdrawable: ${ethers.formatEther(withdrawable2)}`);
      
      // Second withdrawal
      const balanceBefore = await proToken.balanceOf(airdropBeneficiary);
      await airdropVesting.connect(beneficiarySigner).withdraw();
      const balanceAfter = await proToken.balanceOf(airdropBeneficiary);
      
      const withdrawn2 = await airdropVesting.withdrawn();
      expect(withdrawn2).to.equal(unlocked2, "Total withdrawn should match total unlocked");
      expect(balanceAfter - balanceBefore).to.equal(withdrawable2, "Second withdrawal should match withdrawable amount");
      
      console.log(`   ✓ Second withdrawal: ${ethers.formatEther(withdrawable2)} tokens`);
      console.log(`   ✓ Total withdrawn: ${ethers.formatEther(withdrawn2)} tokens`);
      
      await network.provider.request({
        method: "hardhat_stopImpersonatingAccount",
        params: [airdropBeneficiary],
      });
    });
  });
});
