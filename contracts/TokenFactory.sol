// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./BondingCurvePool.sol";
import "./VestingManager.sol";

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
    address public vestingManager;
    
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
        require(_graduationController != address(0), "Bad controller");
        require(_treasury != address(0), "Bad treasury");
        require(_airdropTreasury != address(0), "Bad airdrop");
        require(_platformDevelopmentWallet != address(0), "Bad platform");
        require(_graduationOracle != address(0), "Bad oracle");
        require(_admin != address(0), "Bad admin");
        require(_buybackReserve != address(0), "Bad buyback");
        require(_kaspaSupport != address(0), "Bad kaspa");
        require(_communityRewards != address(0), "Bad community");
        
        // L-2 FIX: Duplicate address validation
        require(_treasury != _admin, "Dup addr");
        require(_treasury != _graduationOracle, "Dup addr");
        require(_airdropTreasury != _platformDevelopmentWallet, "Dup addr");
        
        graduationController = _graduationController;
        treasury = _treasury;
        airdropTreasury = _airdropTreasury;
        platformDevelopmentWallet = _platformDevelopmentWallet;
        graduationOracle = _graduationOracle;
        admin = _admin;
        buybackReserveWallet = _buybackReserve;
        kaspaNetworkSupportWallet = _kaspaSupport;
        communityRewardsWallet = _communityRewards;
        
        // C-1 FIX: Deploy VestingManager with access control
        VestingManager vm = new VestingManager(address(this));
        vestingManager = address(vm);
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
            "Wait"
        );
        
        // Validate inputs
        require(bytes(name).length > 0 && bytes(name).length <= 32, "Bad name");
        require(bytes(symbol).length > 0 && bytes(symbol).length <= 10, "Bad symbol");
        require(totalSupply >= 1_000_000 * 10**18, "Supply low"); // Min 1M tokens
        require(totalSupply <= 1_000_000_000 * 10**18, "Supply high"); // Max 1B tokens
        require(bytes(description).length <= 280, "Desc long"); // Twitter-style limit
        
        // C-3 FIX: Validate vesting parameters BEFORE deploying pool (avoid wasted gas)
        if (reservedPercentage > 0) {
            require(reservedPercentage <= 25, "Vesting exceeds 25%");
            uint256 totalAllocations = uint256(airdropsAllocation) + uint256(marketingAllocation) + uint256(teamAllocation);
            require(totalAllocations == 100, "Allocations must sum to exactly 100%");
            require(totalAllocations > 0, "Must have at least one allocation");
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
            VestingManager.VestingContracts memory vesting = VestingManager(vestingManager).deployVestingContracts(
                poolAddress,
                totalSupply,
                reservedPercentage,
                airdropsAllocation,
                marketingAllocation,
                teamAllocation,
                airdropTreasury,
                msg.sender
            );
            
            airdropVestingAddress = vesting.airdropVesting;
            marketingVestingAddress = vesting.marketingVesting;
            teamVestingAddress = vesting.teamVesting;
            
            if (vesting.airdropTokens > 0) {
                pool.transferReserveToVesting(
                    airdropVestingAddress,
                    vesting.airdropTokens,
                    BondingCurvePool.VestingType.Airdrop
                );
                require(
                    IERC20(poolAddress).balanceOf(airdropVestingAddress) == vesting.airdropTokens,
                    "Airdrop err"
                );
            }
            
            if (vesting.marketingTokens > 0) {
                pool.transferReserveToVesting(
                    marketingVestingAddress,
                    vesting.marketingTokens,
                    BondingCurvePool.VestingType.Marketing
                );
                require(
                    IERC20(poolAddress).balanceOf(marketingVestingAddress) == vesting.marketingTokens,
                    "Marketing err"
                );
            }
            
            if (vesting.teamTokens > 0) {
                pool.transferReserveToVesting(
                    teamVestingAddress,
                    vesting.teamTokens,
                    BondingCurvePool.VestingType.Team
                );
                require(
                    IERC20(poolAddress).balanceOf(teamVestingAddress) == vesting.teamTokens,
                    "Team err"
                );
            }
            
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
        require(newCooldown <= 3600, "CD long"); // Max 1 hour
        deploymentCooldown = newCooldown;
        emit DeploymentCooldownUpdated(newCooldown);
    }

    // Update graduation controller address
    function setGraduationController(address newController) external onlyOwner {
        require(newController != address(0), "Bad ctrl");
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
        require(offset < deployedTokens.length, "Bad offset");
        
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
}
