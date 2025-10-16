// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./BondingCurvePool.sol";
import "./VestingDeployer.sol";

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
    address public vestingDeployer;
    
    // Anti-spam configuration
    uint256 public deploymentCooldown = 60; // 60 seconds between deployments per user
    mapping(address => uint256) public lastDeploymentTime;
    
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
        address _communityRewards,
        address _vestingDeployer
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
        require(_vestingDeployer != address(0), "Bad vesting deployer");
        
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
        vestingDeployer = _vestingDeployer;
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
            
            // N-2 FIX: Add individual allocation bounds checks for clarity
            require(airdropsAllocation <= 100, "Airdrop allocation > 100%");
            require(marketingAllocation <= 100, "Marketing allocation > 100%");
            require(teamAllocation <= 100, "Team allocation > 100%");
            
            uint256 totalAllocations = uint256(airdropsAllocation) + uint256(marketingAllocation) + uint256(teamAllocation);
            require(totalAllocations == 100, "Allocations must sum to exactly 100%");
            
            // Require all three allocations to be non-zero to ensure all vesting contracts are deployed
            // This prevents zero addresses in VestingDeployed event
            require(airdropsAllocation > 0, "Airdrop allocation must be > 0%");
            require(marketingAllocation > 0, "Marketing allocation must be > 0%");
            require(teamAllocation > 0, "Team allocation must be > 0%");
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
            // Automatic beneficiary logic (no user input required)
            address airdropBeneficiary = airdropTreasury;   // Platform wallet for airdrops
            address marketingBeneficiary = msg.sender;       // Creator wallet
            address teamBeneficiary = msg.sender;            // Creator wallet
            
            uint256 totalVesting = totalSupply * reservedPercentage / 100;
            
            // Calculate token amounts
            uint256 airdropTokens = totalVesting * airdropsAllocation / 100;
            uint256 marketingTokens = totalVesting * marketingAllocation / 100;
            uint256 teamTokens = totalVesting * teamAllocation / 100;
            
            // Minimum allocation validation
            if (airdropTokens > 0) {
                require(airdropTokens >= 100 * 10**18, "Airdrop allocation too small for daily unlocks");
            }
            if (marketingTokens > 0) {
                require(marketingTokens >= 100 * 10**18, "Marketing allocation too small for monthly unlocks");
            }
            if (teamTokens > 0) {
                require(teamTokens >= 100 * 10**18, "Team allocation too small for vesting schedule");
            }
            
            // Deploy vesting contracts via VestingDeployer (reduces factory size)
            (airdropVestingAddress, marketingVestingAddress, teamVestingAddress) = 
                VestingDeployer(vestingDeployer).deployVestingContracts(
                    poolAddress,
                    airdropBeneficiary,
                    marketingBeneficiary,
                    teamBeneficiary,
                    airdropTokens,
                    marketingTokens,
                    teamTokens,
                    block.timestamp
                );
            
            // Transfer tokens to vesting contracts
            if (airdropTokens > 0) {
                pool.transferReserveToVesting(airdropVestingAddress, airdropTokens);
                require(
                    IERC20(poolAddress).balanceOf(airdropVestingAddress) == airdropTokens,
                    "Airdrop vesting underfunded"
                );
            }
            
            if (marketingTokens > 0) {
                pool.transferReserveToVesting(marketingVestingAddress, marketingTokens);
                require(
                    IERC20(poolAddress).balanceOf(marketingVestingAddress) == marketingTokens,
                    "Marketing vesting underfunded"
                );
            }
            
            if (teamTokens > 0) {
                pool.transferReserveToVesting(teamVestingAddress, teamTokens);
                require(
                    IERC20(poolAddress).balanceOf(teamVestingAddress) == teamTokens,
                    "Team vesting underfunded"
                );
            }
            
            // Finalize vesting setup
            pool.finalizeVestingSetup();
        }
        
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

    // Check if user can deploy (cooldown check)
    function canDeploy(address user) external view returns (bool) {
        return block.timestamp >= lastDeploymentTime[user] + deploymentCooldown;
    }
}
