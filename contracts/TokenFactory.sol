// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./BondingCurvePool.sol";

contract TokenFactory is Ownable, Pausable, ReentrancyGuard {
    // Contract addresses
    address public graduationController;
    address public treasury;
    address public airdropTreasury;
    address public platformDevelopmentWallet;
    
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

    constructor(
        address _graduationController,
        address _treasury,
        address _airdropTreasury,
        address _platformDevelopmentWallet
    ) {
        require(_graduationController != address(0), "Invalid graduation controller");
        require(_treasury != address(0), "Invalid treasury");
        require(_airdropTreasury != address(0), "Invalid airdrop treasury");
        require(_platformDevelopmentWallet != address(0), "Invalid platform wallet");
        
        graduationController = _graduationController;
        treasury = _treasury;
        airdropTreasury = _airdropTreasury;
        platformDevelopmentWallet = _platformDevelopmentWallet;
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
        bool antiBotEnabled
    ) external nonReentrant whenNotPaused returns (address) {
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
        
        // Deploy BondingCurvePool contract (which is also the ERC-20 token)
        BondingCurvePool pool = new BondingCurvePool(
            name,
            symbol,
            totalSupply,
            msg.sender, // creator
            treasury,
            airdropTreasury,
            platformDevelopmentWallet,
            antiBotEnabled
        );
        
        address poolAddress = address(pool);
        
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
        
        return poolAddress;
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
}
