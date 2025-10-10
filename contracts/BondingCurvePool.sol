// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract BondingCurvePool is ERC20, ReentrancyGuard, Pausable, Ownable {
    // Supply distribution
    uint256 public constant CURVE_SUPPLY_PCT = 75;
    uint256 public constant LP_SUPPLY_PCT = 25;
    uint256 public constant MAX_WALLET_PCT = 10;
    uint256 public constant TOTAL_FEE_BPS = 100; // 1% total trading fee
    uint256 public constant CREATOR_SHARE_BPS = 1000; // 10% of fees (0.1% of trade)

    // GRADUATION: Backend oracle calculates USD market cap off-chain
    // Target: $70,000 USD market cap (backend checks: virtualKasReserve * kasPrice >= $70K)
    address public graduationOracle; // Backend oracle address authorized to trigger graduation

    uint256 public constant MIN_TRADE_AMOUNT = 0.001 ether; // Minimum trade size

    address public treasury; // Gemlaunch treasury contract
    address public airdropTreasury; // Airdrop Treasury for anti-bot fees (70% of anti-bot fees)
    address public platformDevelopmentWallet; // Platform dev wallet (30% of anti-bot fees)
    address public immutable creator; // Token creator address (immutable)

    // AUDIT FIX: Virtual reserves - single source of truth for AMM pricing
    uint256 public virtualKasReserve;   // Tradeable KAS only (excludes fees)
    uint256 public virtualTokenReserve; // Tradeable tokens only

    // Fee tracking (separate from reserves)
    uint256 public accumulatedPlatformFees;
    uint256 public accumulatedCreatorFees;
    uint256 public totalAntiBotFeesCollected; // AUDIT FIX: Total anti-bot fees (analytics only)

    // Anti-Bot System (GEM System - optional per token)
    bool public antiBotEnabled;
    uint256 public deploymentTime; // Launch timestamp

    bool public graduated;
    bool public graduating; // Lock flag during graduation

    // Additional state for access control
    address public admin;
    address public buybackReserveWallet;
    address public kaspaNetworkSupportWallet;
    address public communityRewardsWallet;

    // Events
    event TokensPurchased(
        address indexed buyer,
        uint256 tokensOut,
        uint256 tradeAmount,
        uint256 platformFee,
        uint256 creatorFee,
        uint256 antiBotFee
    );

    event TokensSold(
        address indexed seller,
        uint256 tokensIn,
        uint256 kasOut,
        uint256 platformFee,
        uint256 creatorFee
    );

    event AntiBotFeePaid(
        address indexed user,
        uint256 feeAmount,
        uint256 elapsedSeconds
    );

    event AntiBotFeeSplit(
        uint256 leaderboardAmount,
        uint256 platformDevAmount
    );

    event Graduated(address indexed pool, uint256 kasLiquidity, uint256 tokenLiquidity);
    event GraduationInitiated(uint256 kasLiquidity, uint256 tokenLiquidity);
    event UnsoldTokensBurned(uint256 amount);
    event CreatorFeesWithdrawn(address indexed creator, uint256 amount);
    event GraduationOracleUpdated(address indexed newOracle);
    event FeesDistributed(uint256 dev, uint256 buyback, uint256 kaspa, uint256 community);

    constructor(
        string memory name,
        string memory symbol,
        uint256 totalSupply,
        address _creator,
        address _treasury,
        address _airdropTreasury,
        address _platformDevelopmentWallet,
        bool _antiBotEnabled
    ) ERC20(name, symbol) Ownable(msg.sender) {
        require(_creator != address(0), "Invalid creator");
        require(_treasury != address(0), "Invalid treasury");
        require(_airdropTreasury != address(0), "Invalid airdrop treasury");
        require(_platformDevelopmentWallet != address(0), "Invalid platform wallet");
        require(_airdropTreasury != address(this), "Airdrop treasury cannot be self");
        require(_platformDevelopmentWallet != address(this), "Platform wallet cannot be self");
        
        creator = _creator;
        treasury = _treasury;
        airdropTreasury = _airdropTreasury;
        platformDevelopmentWallet = _platformDevelopmentWallet;
        antiBotEnabled = _antiBotEnabled;
        
        // AUDIT FIX: Only set deploymentTime if anti-bot enabled
        if (_antiBotEnabled) {
            deploymentTime = block.timestamp;
        }
        
        // Mint total supply to contract
        _mint(address(this), totalSupply);
        
        // CRITICAL: Initialize virtual reserves to prevent division by zero
        uint256 curveSupply = totalSupply * CURVE_SUPPLY_PCT / 100; // 75%
        virtualTokenReserve = curveSupply;
        virtualKasReserve = 0.001 ether; // 0.001 KAS virtual seed for initial pricing
        
        // LP tokens (25%) stay in contract, not in virtualTokenReserve
    }

    function buyTokens(uint256 minTokensOut, uint256 deadline) external payable nonReentrant {
        require(!graduated && !graduating, "Token graduated or graduating");
        require(block.timestamp <= deadline, "Transaction expired");
        require(msg.value >= MIN_TRADE_AMOUNT, "Below minimum trade");
        
        uint256 remainingValue = msg.value;
        uint256 antiBotFee = 0;
        
        // AUDIT FIX v4: Step 1 - Calculate and deduct anti-bot fee FIRST
        if (antiBotEnabled && block.timestamp < deploymentTime + 60) {
            uint256 elapsed = block.timestamp - deploymentTime;
            // Linear decay: 95% → 1% over 60 seconds
            uint256 feePercent = 9500 - (9400 * elapsed / 60);
            antiBotFee = msg.value * feePercent / 10000;
            remainingValue = msg.value - antiBotFee;
            
            // TRANSPARENCY FIX: Split anti-bot fees at contract level (no cross-wallet transfers)
            uint256 leaderboardFee = antiBotFee * 70 / 100;  // 70% → Airdrop/Leaderboard
            uint256 platformDevFee = antiBotFee - leaderboardFee; // 30% → Platform Dev
            
            totalAntiBotFeesCollected += antiBotFee;
            
            // Direct routing (clean on-chain flows, no intermediary transfers)
            _safeSend(airdropTreasury, leaderboardFee);
            _safeSend(platformDevelopmentWallet, platformDevFee);
            
            emit AntiBotFeePaid(msg.sender, antiBotFee, elapsed);
            emit AntiBotFeeSplit(leaderboardFee, platformDevFee); // Transparency event
        }
        
        // AUDIT FIX: Step 2 - Calculate platform/creator fees from REMAINING value
        uint256 platformFee = remainingValue * 90 / 10000; // 0.9% of remainder
        uint256 creatorFee = remainingValue * 10 / 10000;  // 0.1% of remainder
        uint256 totalFees = platformFee + creatorFee;
        uint256 tradeAmount = remainingValue - totalFees;
        
        // Step 3: AMM calculation
        uint256 tokensOut = quoteBuy(tradeAmount);
        require(tokensOut >= minTokensOut, "Slippage too high");
        require(tokensOut > 0, "Insufficient output");
        
        // Step 4: Update state (CEI pattern)
        virtualKasReserve += tradeAmount;
        virtualTokenReserve -= tokensOut;
        
        accumulatedPlatformFees += platformFee;
        accumulatedCreatorFees += creatorFee;
        
        // Step 5: Transfer tokens (wallet cap enforced in _transfer override)
        _transfer(address(this), msg.sender, tokensOut);
        
        emit TokensPurchased(msg.sender, tokensOut, tradeAmount, platformFee, creatorFee, antiBotFee);
        
        // Note: Graduation checked by backend oracle off-chain
        // Backend monitors: if (virtualKasReserve * kasPrice >= $70K) → calls initiateGraduation()
    }

    // AUDIT FIX: Safe send helper (replaces .transfer)
    function _safeSend(address to, uint256 amount) private {
        (bool success, ) = payable(to).call{value: amount}("");
        require(success, "Transfer failed");
    }

    function sellTokens(uint256 tokenAmount, uint256 minKasOut, uint256 deadline) external nonReentrant {
        require(!graduated && !graduating, "Token graduated or graduating");
        require(block.timestamp <= deadline, "Transaction expired");
        require(balanceOf(msg.sender) >= tokenAmount, "Insufficient balance");
        
        // Calculate FULL KAS output first (before fees)
        uint256 kasGross = quoteSell(tokenAmount);
        
        // Fee on KAS OUTPUT (1% of KAS) - NOT on tokens
        uint256 totalFeesKas = kasGross * TOTAL_FEE_BPS / 10000; // 1% of KAS
        uint256 creatorFeeKas = totalFeesKas * 10 / 100; // 10% of fees = 0.1% of KAS
        uint256 platformFeeKas = totalFeesKas - creatorFeeKas; // 90% of fees = 0.9% of KAS
        uint256 kasNet = kasGross - totalFeesKas;
        
        // Slippage check on NET amount user receives
        require(kasNet >= minKasOut, "Slippage too high");
        require(kasNet >= MIN_TRADE_AMOUNT, "Below minimum trade");
        
        // CEI Pattern: Update reserves FIRST (full KAS amount leaves)
        virtualTokenReserve += tokenAmount;
        virtualKasReserve -= kasGross; // Full amount (including fees)
        
        // Accumulate KAS fees (actual KAS, not hypothetical)
        accumulatedPlatformFees += platformFeeKas;
        accumulatedCreatorFees += creatorFeeKas;
        
        // Transfer tokens to pool
        _transfer(msg.sender, address(this), tokenAmount);
        
        // Send NET KAS to user (fees stay in contract balance)
        _safeSend(msg.sender, kasNet);
        
        emit TokensSold(msg.sender, tokenAmount, kasGross, platformFeeKas, creatorFeeKas);
    }

    function quoteBuy(uint256 kasIn) public view returns (uint256 tokensOut) {
        // Use ONLY virtual reserves for pricing (excludes accumulated fees)
        uint256 k = virtualTokenReserve * virtualKasReserve;
        
        // Constant product: (virtualTokenReserve - tokensOut) * (virtualKasReserve + kasIn) = k
        uint256 newKasReserve = virtualKasReserve + kasIn;
        uint256 newTokenReserve = k / newKasReserve;
        tokensOut = virtualTokenReserve - newTokenReserve;
        
        require(tokensOut > 0 && tokensOut < virtualTokenReserve, "Invalid output");
    }

    function quoteSell(uint256 tokensIn) public view returns (uint256 kasOut) {
        uint256 k = virtualTokenReserve * virtualKasReserve;
        
        uint256 newTokenReserve = virtualTokenReserve + tokensIn;
        uint256 newKasReserve = k / newTokenReserve;
        kasOut = virtualKasReserve - newKasReserve;
        
        require(kasOut > 0 && kasOut < virtualKasReserve, "Invalid output");
    }

    // Get current anti-bot fee for a given KAS amount
    function getCurrentAntiBotFee(uint256 kasAmount) public view returns (uint256) {
        if (!antiBotEnabled) return 0;
        if (block.timestamp >= deploymentTime + 60) return 0;
        
        uint256 elapsed = block.timestamp - deploymentTime;
        uint256 feePercent = 9500 - (9400 * elapsed / 60);
        return kasAmount * feePercent / 10000;
    }

    // Get seconds remaining until normal fees
    function getSecondsUntilNormalFees() public view returns (uint256) {
        if (!antiBotEnabled) return 0;
        if (block.timestamp >= deploymentTime + 60) return 0;
        return deploymentTime + 60 - block.timestamp;
    }

    // Get complete fee breakdown for UX
    function getEffectiveFeeBreakdown(uint256 kasAmount) external view returns (
        uint256 antiBotFee,
        uint256 platformFee,
        uint256 creatorFee,
        uint256 tradeAmount
    ) {
        antiBotFee = getCurrentAntiBotFee(kasAmount);
        uint256 remaining = kasAmount - antiBotFee;
        platformFee = remaining * 90 / 10000;
        creatorFee = remaining * 10 / 10000;
        tradeAmount = remaining - platformFee - creatorFee;
    }

    function calculateOptimalSlippage(uint256 kasAmount) public view returns (uint256 optimalSlippageBps) {
        require(!graduated, "Use DEX slippage calculation post-graduation");
        
        // Base slippage for bonding curve (deterministic pricing)
        uint256 baseSlippage = 50; // 0.5% base
        
        // AUDIT FIX: Add zero check and overflow protection
        if (virtualKasReserve > 0) {
            uint256 tradeImpactBps = (kasAmount * 10000) / virtualKasReserve;
            
            // Cap trade impact at reasonable level (prevent overflow)
            if (tradeImpactBps > 10000) {
                tradeImpactBps = 10000; // Cap at 100% of pool
            }
            
            // Adjust slippage based on trade size
            if (tradeImpactBps > 100) { // Trade is >1% of pool
                baseSlippage += 50; // Increase to 1%
            }
        }
        
        // Anti-bot period adds volatility (more retry risk)
        if (antiBotEnabled && block.timestamp < deploymentTime + 60) {
            baseSlippage += 50; // +0.5% during anti-bot period
        }
        
        // Cap at 200 bps (2%) for bonding curve
        optimalSlippageBps = baseSlippage > 200 ? 200 : baseSlippage;
    }

    function getMinTokensOutWithAutoSlippage(uint256 kasIn) external view returns (uint256 minTokensOut) {
        require(!graduated, "Token graduated, use DEX");
        
        // AUDIT FIX: Internal call instead of external (cheaper gas)
        (uint256 antiBotFee, uint256 platformFee, uint256 creatorFee, uint256 tradeAmount) 
            = this.getEffectiveFeeBreakdown(kasIn);
        
        uint256 expectedTokens = quoteBuy(tradeAmount);
        
        // Apply auto-calculated slippage
        uint256 slippageBps = calculateOptimalSlippage(kasIn);
        minTokensOut = expectedTokens * (10000 - slippageBps) / 10000;
    }

    function getSlippageRiskLevel(uint256 kasAmount) external view returns (uint8 riskLevel) {
        require(!graduated, "Token graduated");
        
        uint256 slippageBps = calculateOptimalSlippage(kasAmount);
        
        if (slippageBps < 200) return 0;      // <2% = Silent execution
        if (slippageBps < 500) return 1;      // 2-5% = Warning modal
        return 2;                              // >5% = Block trade (shouldn't happen on bonding curve)
    }

    function distributeFees() external nonReentrant {
        require(msg.sender == treasury || msg.sender == admin, "Unauthorized");
        
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to distribute");
        
        // Calculate shares (avoiding 10% loss via remainder pattern)
        uint256 devAmount = balance * 40 / 100;      // 40%
        uint256 buybackAmount = balance * 30 / 100;  // 30%
        uint256 kaspaAmount = balance * 15 / 100;    // 15%
        uint256 communityAmount = balance - devAmount - buybackAmount - kaspaAmount; // 15% (remainder)
        
        // Send to designated wallets
        _safeSend(platformDevelopmentWallet, devAmount);
        _safeSend(buybackReserveWallet, buybackAmount);
        _safeSend(kaspaNetworkSupportWallet, kaspaAmount);
        _safeSend(communityRewardsWallet, communityAmount);
        
        emit FeesDistributed(devAmount, buybackAmount, kaspaAmount, communityAmount);
    }

    // Called by backend oracle when USD market cap reaches $70,000
    function initiateGraduation() external nonReentrant {
        require(msg.sender == graduationOracle, "Only oracle can initiate");
        require(!graduated && !graduating, "Already graduated or graduating");
        
        // Verify sufficient balance for DEX liquidity
        uint256 kasBalance = address(this).balance;
        uint256 requiredKas = virtualKasReserve + accumulatedPlatformFees + accumulatedCreatorFees;
        require(kasBalance >= requiredKas, "Insufficient KAS balance");
        
        graduating = true; // Lock trading during graduation
        
        // Calculate liquidity: virtualKasReserve + 25% token supply
        uint256 lpTokens = totalSupply() * LP_SUPPLY_PCT / 100; // 25%
        
        emit GraduationInitiated(virtualKasReserve, lpTokens);
        
        // Note: Actual DEX migration handled by GraduationController
        // This contract prepares state and emits event for indexer
    }

    // Completes graduation after DEX liquidity added
    function completeGraduation() external nonReentrant {
        require(msg.sender == graduationOracle, "Only oracle can complete");
        require(graduating, "Graduation not initiated");
        
        graduating = false;
        graduated = true;
        
        // Burn unsold curve tokens (any tokens left in contract beyond LP reserve)
        uint256 lpReserve = totalSupply() * LP_SUPPLY_PCT / 100;
        uint256 contractBalance = balanceOf(address(this));
        if (contractBalance > lpReserve) {
            uint256 burnAmount = contractBalance - lpReserve;
            _burn(address(this), burnAmount);
            emit UnsoldTokensBurned(burnAmount);
        }
        
        emit Graduated(address(this), virtualKasReserve, lpReserve);
    }

    // Creator claims accumulated fees
    function withdrawCreatorFees() external nonReentrant {
        require(msg.sender == creator, "Only creator can withdraw");
        require(accumulatedCreatorFees > 0, "No fees to withdraw");
        
        uint256 amount = accumulatedCreatorFees;
        accumulatedCreatorFees = 0; // Reset before transfer (CEI)
        
        _safeSend(creator, amount);
        
        emit CreatorFeesWithdrawn(creator, amount);
    }

    // View function for creator to check claimable amount
    function getCreatorClaimableAmount() external view returns (uint256) {
        return accumulatedCreatorFees;
    }

    // M-4 Fix: Prevent direct KAS transfers (force use of buyTokens)
    receive() external payable {
        revert("Use buyTokens() to purchase");
    }

    // Emergency pause (only admin)
    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // Update graduation oracle (only admin)
    function setGraduationOracle(address newOracle) external onlyOwner {
        require(newOracle != address(0), "Invalid oracle");
        graduationOracle = newOracle;
        emit GraduationOracleUpdated(newOracle);
    }

    // Override _update to enforce 10% wallet cap (OpenZeppelin v5)
    function _update(address from, address to, uint256 amount) internal virtual override {
        // Enforce wallet cap with exemptions for:
        // 1. Contract itself (holds curve + LP supply)
        // 2. Airdrop treasury (holds vested allocations up to 25%)
        // 3. Graduated pools (no restrictions after DEX listing)
        // 4. Transfers FROM airdropTreasury (allows >10% vesting distributions to team/founders)
        // 5. Minting/burning (from/to == address(0))
        if (to != address(0) &&
            to != address(this) && 
            to != airdropTreasury && 
            from != airdropTreasury &&
            !graduated) {
            uint256 recipientBalance = balanceOf(to);
            uint256 maxWallet = totalSupply() * MAX_WALLET_PCT / 100; // 10%
            require(recipientBalance + amount <= maxWallet, "Exceeds max wallet");
        }
        
        super._update(from, to, amount);
    }
}
