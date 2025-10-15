// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./BondingCurvePool.sol";
import "./AirdropVesting.sol";
import "./LinearVesting.sol";
import "./CliffVesting.sol";

contract TokenFactory is Ownable, Pausable, ReentrancyGuard {
    // Contract addresses
    address public graduationController;
    address public treasury;
    address public airdropTreasury;
    address public platformDevelopmentWallet;
    address public graduationOracle;
    address public admin;
    address public buybackReserveWallet;
    address public kaspaNetworkSupportWallet;
    address public communityRewardsWallet;
    
    // Token registry
    address[] public deployedTokens;
    mapping(address => TokenInfo) public tokens;
    
    // Anti-spam configuration
    uint256 public deploymentCooldown = 60; // 60 seconds between deployments per user
    mapping(address => uint256) public lastDeploymentTime;
    
    struct TokenInfo {
        string name;
        string symbol;
        uint256 totalSupply;
        address creator;
        address poolAddress;
        string description;
        string imageUrl;
        string twitterUrl;
        string telegramUrl;
        string websiteUrl;
        uint256 deployedAt;
        bool antiBotEnabled;
    }
    
    // Events
    event TokenCreated(
        address indexed tokenAddress,
        address indexed poolAddress,
        address indexed creator,
        string name,
        string symbol,
        uint256 totalSupply,
        bool antiBotEnabled,
        uint256 timestamp
    );
    
    event DeploymentCooldownUpdated(uint256 newCooldown);
    event GraduationControllerUpdated(address indexed newController);
    event EmergencyTokenRecovery(address indexed token, uint256 amount);
    event EmergencyKASRecovery(uint256 amount);
    
    event VestingDeployed(
        address indexed token,
        address airdropVesting,
        uint8 airdropAllocation,
        address marketingVesting,
        uint8 marketingAllocation,
        address teamVesting,
        uint8 teamAllocation
    );

    constructor(
        address _graduationController,
        address _treasury,
        address _airdropTreasury,
        address _platformDevelopmentWallet,
        address _graduationOracle,
        address _admin,
        address _buybackReserve,
        address _kaspaSupport,
        address _communityRewards
    ) Ownable(msg.sender) {
        require(_graduationController != address(0), "Invalid graduation controller");
        require(_treasury != address(0), "Invalid treasury");
        require(_airdropTreasury != address(0), "Invalid airdrop treasury");
        require(_platformDevelopmentWallet != address(0), "Invalid platform wallet");
        require(_graduationOracle != address(0), "Invalid graduation oracle");
        require(_admin != address(0), "Invalid admin");
        require(_buybackReserve != address(0), "Invalid buyback reserve");
        require(_kaspaSupport != address(0), "Invalid kaspa support");
        require(_communityRewards != address(0), "Invalid community rewards");
        
        // L-2 FIX: Duplicate address validation
        require(_treasury != _admin, "Treasury cannot be admin");
        require(_treasury != _graduationOracle, "Treasury cannot be oracle");
        require(_airdropTreasury != _platformDevelopmentWallet, "Duplicate wallets");
        
        graduationController = _graduationController;
        treasury = _treasury;
        airdropTreasury = _airdropTreasury;
        platformDevelopmentWallet = _platformDevelopmentWallet;
        graduationOracle = _graduationOracle;
        admin = _admin;
        buybackReserveWallet = _buybackReserve;
        kaspaNetworkSupportWallet = _kaspaSupport;
        communityRewardsWallet = _communityRewards;
    }

    function createToken(
        string memory name,
        string memory symbol,
        uint256 totalSupply,
        string memory description,
        string memory imageUrl,
        string memory twitterUrl,
        string memory telegramUrl,
        string memory websiteUrl,
        bool antiBotEnabled,
        uint8 reservedPercentage,        // 0-25 (vesting %)
        uint8 airdropsAllocation,        // % of vesting reserve
        uint8 marketingAllocation,       // % of vesting reserve
        uint8 teamAllocation             // % of vesting reserve
    ) external nonReentrant whenNotPaused returns (
        address poolAddress,
        address airdropVestingAddress,
        address marketingVestingAddress,
        address teamVestingAddress
    ) {
        // Anti-spam: Enforce deployment cooldown
        require(
            block.timestamp >= lastDeploymentTime[msg.sender] + deploymentCooldown,
            "Deployment cooldown active"
        );
        
        // Validate inputs
        require(bytes(name).length > 0 && bytes(name).length <= 32, "Invalid name length");
        require(bytes(symbol).length > 0 && bytes(symbol).length <= 10, "Invalid symbol length");
        require(totalSupply >= 1_000_000 * 10**18, "Total supply too low"); // Min 1M tokens
        require(totalSupply <= 1_000_000_000 * 10**18, "Total supply too high"); // Max 1B tokens
        require(bytes(description).length <= 280, "Description too long"); // Twitter-style limit
        
        // AUTOMATIC BENEFICIARY LOGIC (No user input required)
        // This is intentional design for simplicity and ease of use:
        // - Airdrop vesting → Platform's airdropTreasury (for system-managed airdrops via chat)
        // - Marketing vesting → msg.sender (creator's wallet)
        // - Team vesting → msg.sender (creator's wallet)
        // Creators can manually transfer tokens later if they want separate wallets
        
        // Validate vesting params
        require(reservedPercentage <= 25, "Vesting exceeds 25%");
        
        if (reservedPercentage > 0) {
            // Allocations must sum to exactly 100%
            uint256 totalAllocations = airdropsAllocation + marketingAllocation + teamAllocation;
            require(totalAllocations == 100, "Allocations must sum to exactly 100%");
        }
        
        // Deploy BondingCurvePool contract (which is also the ERC-20 token)
        BondingCurvePool pool = new BondingCurvePool(
            name,
            symbol,
            totalSupply,
            msg.sender, // creator
            treasury,
            airdropTreasury,
            platformDevelopmentWallet,
            antiBotEnabled,
            graduationOracle,
            admin,
            buybackReserveWallet,
            kaspaNetworkSupportWallet,
            communityRewardsWallet,
            reservedPercentage  // NEW: vesting percentage
        );
        
        poolAddress = address(pool);
        
        // Deploy vesting contracts if PRO token
        if (reservedPercentage > 0) {
            uint256 totalVesting = totalSupply * reservedPercentage / 100;
            
            // Calculate token amounts
            uint256 airdropTokens = totalVesting * airdropsAllocation / 100;
            uint256 marketingTokens = totalVesting * marketingAllocation / 100;
            uint256 teamTokens = totalVesting * teamAllocation / 100;
            
            // Minimum allocation validation for meaningful unlocks
            if (airdropTokens > 0) {
                require(airdropTokens >= 100 * 10**18, "Airdrop allocation too small for daily unlocks");
            }
            if (marketingTokens > 0) {
                require(marketingTokens >= 100 * 10**18, "Marketing allocation too small for monthly unlocks");
            }
            if (teamTokens > 0) {
                require(teamTokens >= 100 * 10**18, "Team allocation too small for vesting schedule");
            }
            
            // Deploy airdrop vesting (platform wallet)
            if (airdropTokens > 0) {
                AirdropVesting av = new AirdropVesting(
                    poolAddress,
                    airdropTreasury,  // Platform wallet
                    airdropTokens
                );
                airdropVestingAddress = address(av);
                pool.transferReserveToVesting(airdropVestingAddress, airdropTokens);
                
                require(
                    IERC20(poolAddress).balanceOf(airdropVestingAddress) == airdropTokens,
                    "Airdrop vesting underfunded"
                );
            }
            
            // Deploy marketing vesting (creator wallet)
            if (marketingTokens > 0) {
                LinearVesting mv = new LinearVesting(
                    poolAddress,
                    msg.sender,  // Creator wallet
                    marketingTokens,
                    12  // 12 months
                );
                marketingVestingAddress = address(mv);
                pool.transferReserveToVesting(marketingVestingAddress, marketingTokens);
                
                require(
                    IERC20(poolAddress).balanceOf(marketingVestingAddress) == marketingTokens,
                    "Marketing vesting underfunded"
                );
            }
            
            // Deploy team vesting (creator wallet)
            if (teamTokens > 0) {
                CliffVesting tv = new CliffVesting(
                    poolAddress,
                    msg.sender,  // Creator wallet
                    teamTokens,
                    6,   // 6 month cliff
                    18   // 18 month vesting
                );
                teamVestingAddress = address(tv);
                pool.transferReserveToVesting(teamVestingAddress, teamTokens);
                
                require(
                    IERC20(poolAddress).balanceOf(teamVestingAddress) == teamTokens,
                    "Team vesting underfunded"
                );
            }
            
            // Finalize vesting setup
            pool.finalizeVestingSetup();
        }
        
        // Store token metadata
        tokens[poolAddress] = TokenInfo({
            name: name,
            symbol: symbol,
            totalSupply: totalSupply,
            creator: msg.sender,
            poolAddress: poolAddress,
            description: description,
            imageUrl: imageUrl,
            twitterUrl: twitterUrl,
            telegramUrl: telegramUrl,
            websiteUrl: websiteUrl,
            deployedAt: block.timestamp,
            antiBotEnabled: antiBotEnabled
        });
        
        deployedTokens.push(poolAddress);
        lastDeploymentTime[msg.sender] = block.timestamp;
        
        emit TokenCreated(
            poolAddress,
            poolAddress,
            msg.sender,
            name,
            symbol,
            totalSupply,
            antiBotEnabled,
            block.timestamp
        );
        
        // Emit vesting event if PRO token
        if (reservedPercentage > 0) {
            emit VestingDeployed(
                poolAddress,
                airdropVestingAddress,
                airdropsAllocation,
                marketingVestingAddress,
                marketingAllocation,
                teamVestingAddress,
                teamAllocation
            );
        }
        
        return (poolAddress, airdropVestingAddress, marketingVestingAddress, teamVestingAddress);
    }

    // Update deployment cooldown (anti-spam control)
    function setDeploymentCooldown(uint256 newCooldown) external onlyOwner {
        require(newCooldown <= 3600, "Cooldown too long"); // Max 1 hour
        deploymentCooldown = newCooldown;
        emit DeploymentCooldownUpdated(newCooldown);
    }

    // Update graduation controller address
    function setGraduationController(address newController) external onlyOwner {
        require(newController != address(0), "Invalid controller");
        graduationController = newController;
        emit GraduationControllerUpdated(newController);
    }

    // Emergency pause (stops new token creation)
    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // Emergency token recovery (if tokens accidentally sent to factory)
    function emergencyWithdrawToken(address token, uint256 amount) external onlyOwner {
        require(token != address(0), "Invalid token");
        IERC20(token).transfer(owner(), amount);
        emit EmergencyTokenRecovery(token, amount);
    }

    // Emergency KAS recovery (if KAS accidentally sent to factory)
    function emergencyWithdrawKAS(uint256 amount) external onlyOwner {
        require(address(this).balance >= amount, "Insufficient balance");
        payable(owner()).transfer(amount);
        emit EmergencyKASRecovery(amount);
    }

    // Get total number of deployed tokens
    function getDeployedTokenCount() external view returns (uint256) {
        return deployedTokens.length;
    }

    // Get token info by address
    function getTokenInfo(address tokenAddress) external view returns (TokenInfo memory) {
        return tokens[tokenAddress];
    }

    // Get all deployed tokens (paginated to prevent gas issues)
    function getDeployedTokens(uint256 offset, uint256 limit) external view returns (address[] memory) {
        require(offset < deployedTokens.length, "Offset out of bounds");
        
        uint256 end = offset + limit;
        if (end > deployedTokens.length) {
            end = deployedTokens.length;
        }
        
        address[] memory result = new address[](end - offset);
        for (uint256 i = offset; i < end; i++) {
            result[i - offset] = deployedTokens[i];
        }
        
        return result;
    }

    // Check if user can deploy (cooldown check)
    function canDeploy(address user) external view returns (bool) {
        return block.timestamp >= lastDeploymentTime[user] + deploymentCooldown;
    }

    // Get seconds until user can deploy again
    function getSecondsUntilNextDeployment(address user) external view returns (uint256) {
        uint256 nextDeploymentTime = lastDeploymentTime[user] + deploymentCooldown;
        if (block.timestamp >= nextDeploymentTime) {
            return 0;
        }
        return nextDeploymentTime - block.timestamp;
    }

    // Allow factory to receive KAS (for emergency recovery scenarios)
    receive() external payable {}
}
