// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./BondingCurvePool.sol";

// Kaspa Finance interfaces (Uniswap V3 architecture)
interface INonfungiblePositionManager {
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
    );
}

interface IWKAS {
    function deposit() external payable;
    function approve(address spender, uint256 amount) external returns (bool);
}

contract GraduationController is Ownable, ReentrancyGuard {
    // Kaspa Finance integration
    address public immutable kaspaFinancePositionManager;
    address public immutable kaspaFinanceWKAS;
    
    // Oracle for USD price checks (backend service)
    address public graduationOracle;
    
    // Graduation tracking
    mapping(address => bool) public hasGraduated;
    mapping(address => uint256) public graduationTimestamp;
    mapping(address => uint256) public liquidityPositionId; // Uniswap V3 NFT position ID
    
    // Constants
    uint24 public constant POOL_FEE_TIER = 2500; // 0.25% fee tier
    int24 public constant FULL_RANGE_TICK_LOWER = -887220; // Full range position
    int24 public constant FULL_RANGE_TICK_UPPER = 887220;
    
    // Events
    event GraduationInitiated(
        address indexed tokenAddress,
        uint256 kasLiquidity,
        uint256 tokenLiquidity,
        uint256 timestamp
    );
    
    event GraduationCompleted(
        address indexed tokenAddress,
        uint256 liquidityPositionId,
        uint256 kasAdded,
        uint256 tokensAdded,
        uint256 timestamp
    );
    
    event GraduationFailed(
        address indexed tokenAddress,
        string reason,
        uint256 timestamp
    );
    
    event OracleUpdated(address indexed newOracle);

    constructor(
        address _kaspaFinancePositionManager,
        address _kaspaFinanceWKAS,
        address _graduationOracle
    ) Ownable(msg.sender) {
        require(_kaspaFinancePositionManager != address(0), "Invalid position manager");
        require(_kaspaFinanceWKAS != address(0), "Invalid WKAS");
        require(_graduationOracle != address(0), "Invalid oracle");
        
        kaspaFinancePositionManager = _kaspaFinancePositionManager;
        kaspaFinanceWKAS = _kaspaFinanceWKAS;
        graduationOracle = _graduationOracle;
    }

    // Allow contract to receive KAS for graduation liquidity
    receive() external payable {}

    // Step 1: Initiate graduation (called by backend oracle when USD threshold reached)
    function initiateGraduation(address tokenAddress) external nonReentrant {
        require(msg.sender == graduationOracle, "Only oracle can initiate");
        require(!hasGraduated[tokenAddress], "Already graduated");
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        
        // Trigger graduation on the pool contract
        try pool.initiateGraduation() {
            emit GraduationInitiated(
                tokenAddress,
                pool.virtualKasReserve(),
                pool.totalSupply() * 25 / 100, // 25% LP supply
                block.timestamp
            );
        } catch Error(string memory reason) {
            emit GraduationFailed(tokenAddress, reason, block.timestamp);
            revert(reason);
        }
    }

    // Step 2: Complete graduation (add liquidity to Kaspa Finance DEX)
    function completeGraduation(address tokenAddress) external nonReentrant {
        require(msg.sender == graduationOracle, "Only oracle can complete");
        require(!hasGraduated[tokenAddress], "Already graduated");
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        require(pool.graduating(), "Graduation not initiated");
        
        // Get liquidity amounts (KAS was already transferred during initiation)
        uint256 kasLiquidity = address(this).balance; // Use actual KAS balance controller has
        require(kasLiquidity > 0, "No KAS received");
        
        uint256 tokenLiquidity = pool.totalSupply() * 25 / 100; // 25% of total supply
        
        // Transfer tokens from pool to this contract
        uint256 allowance = IERC20(tokenAddress).allowance(address(pool), address(this));
        require(allowance >= tokenLiquidity, "Insufficient approval");
        
        IERC20(tokenAddress).transferFrom(address(pool), address(this), tokenLiquidity);
        
        // Wrap KAS to WKAS for Uniswap V3 pool
        IWKAS wkas = IWKAS(kaspaFinanceWKAS);
        wkas.deposit{value: kasLiquidity}();
        
        // Approve position manager to spend tokens
        IERC20(tokenAddress).approve(kaspaFinancePositionManager, tokenLiquidity);
        wkas.approve(kaspaFinancePositionManager, kasLiquidity);
        
        // Determine token ordering (token0 < token1)
        (address token0, address token1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenAddress, kaspaFinanceWKAS)
            : (kaspaFinanceWKAS, tokenAddress);
        
        (uint256 amount0, uint256 amount1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenLiquidity, kasLiquidity)
            : (kasLiquidity, tokenLiquidity);
        
        // Create full-range liquidity position on Kaspa Finance (Uniswap V3)
        INonfungiblePositionManager.MintParams memory params = INonfungiblePositionManager.MintParams({
            token0: token0,
            token1: token1,
            fee: POOL_FEE_TIER, // 0.25% fee tier
            tickLower: FULL_RANGE_TICK_LOWER,
            tickUpper: FULL_RANGE_TICK_UPPER,
            amount0Desired: amount0,
            amount1Desired: amount1,
            amount0Min: amount0 * 95 / 100, // 5% slippage tolerance
            amount1Min: amount1 * 95 / 100,
            recipient: address(this), // Controller holds the LP NFT
            deadline: block.timestamp + 300 // 5 minute deadline
        });
        
        (uint256 positionId, , uint256 actualAmount0, uint256 actualAmount1) = 
            INonfungiblePositionManager(kaspaFinancePositionManager).mint(params);
        
        // Mark as graduated
        hasGraduated[tokenAddress] = true;
        graduationTimestamp[tokenAddress] = block.timestamp;
        liquidityPositionId[tokenAddress] = positionId;
        
        // Complete graduation on pool contract (locks trading, burns unsold tokens)
        pool.completeGraduation();
        
        emit GraduationCompleted(
            tokenAddress,
            positionId,
            tokenAddress < kaspaFinanceWKAS ? actualAmount1 : actualAmount0, // KAS amount
            tokenAddress < kaspaFinanceWKAS ? actualAmount0 : actualAmount1, // Token amount
            block.timestamp
        );
    }

    // Update graduation oracle
    function setGraduationOracle(address newOracle) external onlyOwner {
        require(newOracle != address(0), "Invalid oracle");
        graduationOracle = newOracle;
        emit OracleUpdated(newOracle);
    }

    // Emergency: Reverse failed graduation (only if DEX liquidity not added)
    function emergencyReverseGraduation(address tokenAddress) external onlyOwner {
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        require(pool.graduating(), "Not graduating");
        require(!hasGraduated[tokenAddress], "Already graduated");
        
        // This would need a special function in BondingCurvePool to reverse graduation
        // For now, this is a placeholder for emergency controls
        
        emit GraduationFailed(tokenAddress, "Emergency reversal by admin", block.timestamp);
    }

    // Withdraw accidentally sent tokens (emergency recovery)
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner(), amount);
    }

    // Check if token has graduated
    function isGraduated(address tokenAddress) external view returns (bool) {
        return hasGraduated[tokenAddress];
    }

    // Get graduation info
    function getGraduationInfo(address tokenAddress) external view returns (
        bool graduated,
        uint256 timestamp,
        uint256 positionId
    ) {
        return (
            hasGraduated[tokenAddress],
            graduationTimestamp[tokenAddress],
            liquidityPositionId[tokenAddress]
        );
    }
}
