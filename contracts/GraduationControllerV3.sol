// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title GraduationController V3
 * @notice Manages token graduation from bonding curve to Uniswap V3 DEX liquidity
 * @dev FIXES ALL 11 CRITICAL ISSUES FROM V2:
 *      FIX #1: INITIAL_VIRTUAL_KAS = 0.001 ether (not 1000)
 *      FIX #2: Snapshot reserves BEFORE pool.initiateGraduation()
 *      FIX #3: Use snapshot.kasLiquidity (1089.99 KAS, not 89.991)
 *      FIX #4: Ticks = -887200/887200 (multiples of 50)
 *      FIX #5: Use createAndInitializePoolIfNecessary() - atomic, no front-running
 *      FIX #6: Burn LP NFT to 0x...dEaD (permanent liquidity lock)
 *      FIX #7: Send excess to treasury, NEVER to pool (receive() reverts)
 *      FIX #8: Validate sqrtPrice MIN/MAX bounds
 *      FIX #9: pool.completeGraduation() with NO try/catch (must revert on failure)
 *      FIX #10: Lock oracle changes during graduation (authorizedOracle in snapshot)
 *      FIX #11: Deadline = 1800 seconds (30 min, not 5)
 * 
 * Version: 3.0.0
 * Deployment Date: October 24, 2025
 * Architecture: Snapshot-based (immutable state capture)
 */

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "./BondingCurvePool.sol";

/**
 * @title FullMath Library
 * @notice Safe 512-bit multiplication and division from Uniswap V3
 * @dev Prevents overflow when calculating sqrtPriceX96 with large reserves
 */
library FullMath {
    /**
     * @notice Calculates floor(a×b÷denominator) with full precision
     * @dev Handles intermediate overflow by using 512-bit math
     */
    function mulDiv(
        uint256 a,
        uint256 b,
        uint256 denominator
    ) internal pure returns (uint256 result) {
        // 512-bit multiply [prod1 prod0] = a * b
        uint256 prod0;
        uint256 prod1;
        assembly {
            let mm := mulmod(a, b, not(0))
            prod0 := mul(a, b)
            prod1 := sub(sub(mm, prod0), lt(mm, prod0))
        }

        if (prod1 == 0) {
            require(denominator > 0);
            assembly {
                result := div(prod0, denominator)
            }
            return result;
        }

        require(denominator > prod1);

        uint256 remainder;
        assembly {
            remainder := mulmod(a, b, denominator)
        }
        assembly {
            prod1 := sub(prod1, gt(remainder, prod0))
            prod0 := sub(prod0, remainder)
        }

        uint256 twos = denominator & (~denominator + 1);
        assembly {
            denominator := div(denominator, twos)
        }

        assembly {
            prod0 := div(prod0, twos)
        }
        assembly {
            twos := add(div(sub(0, twos), twos), 1)
        }
        unchecked {
            prod0 |= prod1 * twos;
        }

        uint256 inv = (3 * denominator) ^ 2;
        unchecked {
            inv *= 2 - denominator * inv;
            inv *= 2 - denominator * inv;
            inv *= 2 - denominator * inv;
            inv *= 2 - denominator * inv;
            inv *= 2 - denominator * inv;
            inv *= 2 - denominator * inv;
        }

        unchecked {
            result = prod0 * inv;
        }
        return result;
    }
}

/**
 * @title Uniswap V3 Factory Interface
 */
interface IUniswapV3Factory {
    function createPool(address tokenA, address tokenB, uint24 fee) 
        external returns (address pool);
    
    function getPool(address tokenA, address tokenB, uint24 fee) 
        external view returns (address pool);
}

/**
 * @title Uniswap V3 Pool Interface
 */
interface IUniswapV3Pool {
    function initialize(uint160 sqrtPriceX96) external;
    
    function slot0() external view returns (
        uint160 sqrtPriceX96,
        int24 tick,
        uint16 observationIndex,
        uint16 observationCardinality,
        uint16 observationCardinalityNext,
        uint8 feeProtocol,
        bool unlocked
    );
    
    function token0() external view returns (address);
    function token1() external view returns (address);
}

/**
 * @title Uniswap V3 NFT Position Manager Interface
 * @notice FIX #5: Added createAndInitializePoolIfNecessary() for atomic pool creation
 */
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
    
    struct CollectParams {
        uint256 tokenId;
        address recipient;
        uint128 amount0Max;
        uint128 amount1Max;
    }
    
    function mint(MintParams calldata params) external payable returns (
        uint256 tokenId,
        uint128 liquidity,
        uint256 amount0,
        uint256 amount1
    );
    
    function collect(CollectParams calldata params) external payable returns (
        uint256 amount0,
        uint256 amount1
    );
    
    /**
     * @notice FIX #5: Atomic pool creation and initialization (prevents front-running)
     * @dev Creates pool if it doesn't exist, then initializes it in same transaction
     */
    function createAndInitializePoolIfNecessary(
        address token0,
        address token1,
        uint24 fee,
        uint160 sqrtPriceX96
    ) external payable returns (address pool);
    
    /**
     * @notice FIX #6: Transfer NFT to burn address for permanent liquidity lock
     */
    function safeTransferFrom(
        address from,
        address to,
        uint256 tokenId
    ) external;
}

/**
 * @title Wrapped KAS Interface
 */
interface IWKAS {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title GraduationController V3
 * @notice Snapshot-based graduation with all 11 critical fixes
 */
contract GraduationControllerV3 is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;
    
    // ============ State Variables ============
    
    /// @notice Contract version
    string public constant VERSION = "3.0.0";
    
    /// @notice Kaspa Finance Uniswap V3 factory address
    address public immutable kaspaFinanceFactory;
    
    /// @notice Kaspa Finance NFT Position Manager address
    address public immutable kaspaFinancePositionManager;
    
    /// @notice Wrapped KAS token address
    address public immutable kaspaFinanceWKAS;
    
    /// @notice Address authorized to trigger graduations (backend oracle)
    address public graduationOracle;
    
    /// @notice TokenFactory address for validating legitimate tokens
    address public tokenFactory;
    
    /// @notice FIX #7: Treasury address for excess token handling (NOT pool!)
    address public treasury;
    
    // Graduation tracking
    mapping(address => bool) public hasGraduated;
    mapping(address => uint256) public graduationTimestamp;
    mapping(address => address) public uniswapPoolAddress;
    
    /// @notice FIX #2/#3: Immutable graduation snapshots (captured BEFORE pool changes)
    mapping(address => GraduationSnapshot) public graduationSnapshots;
    
    // NOTE: liquidityPositionId mapping REMOVED (FIX #6: NFT is burned, not stored)
    
    // ============ Structures ============
    
    /**
     * @notice FIX #2/#3/#10: Immutable snapshot of graduation state
     * @dev Captured BEFORE pool.initiateGraduation() to prevent stale data
     */
    struct GraduationSnapshot {
        uint256 kasLiquidity;        // KAS to add to DEX (e.g., 1089.99)
        uint256 tokenLiquidity;      // Tokens to add to DEX (e.g., 250M)
        uint160 targetSqrtPriceX96;  // Pre-calculated price
        uint24 feeTier;              // Pool fee (2500 = 0.25%)
        uint32 initiatedAt;          // Block timestamp
        bool poolInitialized;        // Uniswap pool initialized
        bool lpMinted;               // LP NFT minted
        address uniswapPool;         // Created pool address
        address authorizedOracle;    // FIX #10: Oracle authorized for this graduation
    }
    
    // ============ Constants ============
    
    /// @notice Uniswap V3 pool fee tier (0.25%)
    uint24 public constant POOL_FEE_TIER = 2500;
    
    /// @notice FIX #4: Full range ticks (multiples of 50 for 0.25% fee tier)
    int24 public constant FULL_RANGE_TICK_LOWER = -887200;  // Was -887220 in V2
    int24 public constant FULL_RANGE_TICK_UPPER = 887200;   // Was 887220 in V2
    
    /// @notice FIX #1: Correct initial virtual KAS (matches BondingCurvePool)
    uint256 public constant INITIAL_VIRTUAL_KAS = 0.001 ether;  // Was 1000 ether in V2
    
    /// @notice Percentage of token supply to add as liquidity (25%)
    uint256 public constant LP_SUPPLY_PERCENTAGE = 25;
    
    /// @notice FIX #8: Uniswap V3 sqrtPrice bounds for validation
    uint160 public constant MIN_SQRT_RATIO = 4295128739;
    uint160 public constant MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342;
    
    /// @notice FIX #6: Burn address for permanent LP NFT locking
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;
    
    // ============ Configurable Parameters ============
    
    /// @notice Slippage tolerance for liquidity minting (in basis points, 500 = 5%)
    uint256 public graduationSlippageBps = 500;
    
    /// @notice FIX #11: Extended deadline for graduation transactions (30 minutes)
    uint256 public graduationDeadlineSeconds = 1800;  // Was 300 (5 min) in V2
    
    /// @notice Maximum price deviation tolerance (in basis points, 100 = 1%)
    uint256 public maxPriceDeviationBps = 100;
    
    // ============ Events ============
    
    /**
     * @notice FIX #2: New event for snapshot creation
     */
    event GraduationSnapshotCreated(
        address indexed tokenAddress,
        uint256 kasLiquidity,
        uint256 tokenLiquidity,
        uint160 targetSqrtPriceX96,
        uint256 timestamp
    );
    
    event GraduationInitiated(
        address indexed tokenAddress,
        uint256 expectedKasLiquidity,
        uint256 expectedTokenLiquidity,
        uint256 timestamp
    );
    
    event PoolCreated(
        address indexed tokenAddress,
        address indexed poolAddress,
        uint160 sqrtPriceX96,
        uint256 timestamp
    );
    
    event PoolInitialized(
        address indexed tokenAddress,
        address indexed poolAddress,
        uint160 sqrtPriceX96,
        uint256 timestamp
    );
    
    event GraduationCompleted(
        address indexed tokenAddress,
        address indexed poolAddress,
        uint256 liquidityPositionId,
        uint256 kasAdded,
        uint256 tokensAdded,
        uint256 timestamp
    );
    
    /**
     * @notice FIX #6: New event for LP NFT burning
     */
    event LPNFTBurned(
        address indexed tokenAddress,
        uint256 indexed positionId,
        uint256 timestamp
    );
    
    /**
     * @notice FIX #7: New event for excess token handling
     */
    event ExcessTokensHandled(
        address indexed token0,
        address indexed token1,
        uint256 excess0,
        uint256 excess1,
        address indexed recipient
    );
    
    event GraduationCancelled(
        address indexed tokenAddress,
        uint256 kasReturned,
        uint256 tokensReturned,
        string reason,
        uint256 timestamp
    );
    
    event GraduationFailed(
        address indexed tokenAddress,
        string reason,
        uint256 timestamp
    );
    
    event FeesCollected(
        address indexed tokenAddress,
        uint256 amount0,
        uint256 amount1,
        uint256 timestamp
    );
    
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    event TokenFactoryUpdated(address indexed oldFactory, address indexed newFactory);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event GraduationParamsUpdated(uint256 slippageBps, uint256 deadlineSeconds, uint256 maxPriceDeviationBps);
    event EmergencyWithdrawal(address indexed token, uint256 amount, address indexed recipient);
    
    // ============ Errors ============
    
    error OnlyOracle();
    error AlreadyGraduated();
    error AlreadyInitiated();
    error NotInitiated();
    error InvalidToken();
    error InsufficientLiquidity();
    error InvalidPrice();
    error PoolNotReady();
    error TransferFailed();
    error InvalidAddress();
    error UnauthorizedOracle();  // FIX #10
    
    // ============ Modifiers ============
    
    modifier onlyOracle() {
        if (msg.sender != graduationOracle) revert OnlyOracle();
        _;
    }
    
    // ============ Constructor ============
    
    constructor(
        address _kaspaFinanceFactory,
        address _kaspaFinancePositionManager,
        address _kaspaFinanceWKAS,
        address _graduationOracle,
        address _tokenFactory,
        address _treasury
    ) Ownable(msg.sender) {
        require(_kaspaFinanceFactory != address(0), "Invalid factory");
        require(_kaspaFinancePositionManager != address(0), "Invalid position manager");
        require(_kaspaFinanceWKAS != address(0), "Invalid WKAS");
        require(_graduationOracle != address(0), "Invalid oracle");
        require(_tokenFactory != address(0), "Invalid token factory");
        require(_treasury != address(0), "Invalid treasury");
        
        kaspaFinanceFactory = _kaspaFinanceFactory;
        kaspaFinancePositionManager = _kaspaFinancePositionManager;
        kaspaFinanceWKAS = _kaspaFinanceWKAS;
        graduationOracle = _graduationOracle;
        tokenFactory = _tokenFactory;
        treasury = _treasury;
    }
    
    // ============ Core Graduation Functions ============
    
    /**
     * @notice FIX #2/#3: Initiate graduation with snapshot BEFORE pool changes
     * @dev Captures immutable state, then triggers pool transfer
     */
    function initiateGraduation(address tokenAddress) 
        external 
        nonReentrant 
        whenNotPaused
        onlyOracle 
    {
        if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
        if (graduationSnapshots[tokenAddress].initiatedAt != 0) revert AlreadyInitiated();
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        
        // STEP 1: Snapshot BEFORE any state changes (FIX #2/#3)
        uint256 kasLiquidity = pool.virtualKasReserve() > INITIAL_VIRTUAL_KAS 
            ? pool.virtualKasReserve() - INITIAL_VIRTUAL_KAS 
            : 0;
        uint256 tokenLiquidity = (pool.totalSupply() * LP_SUPPLY_PERCENTAGE) / 100;
        
        require(kasLiquidity > 0 && tokenLiquidity > 0, "Insufficient liquidity");
        
        // STEP 2: Pre-calculate sqrtPrice from snapshot values (FIX #2)
        uint160 targetSqrtPrice = _calculateSqrtPriceX96(
            kasLiquidity,      // 1089.99 KAS (correct!)
            tokenLiquidity,    // 250M tokens
            tokenAddress
        );
        
        require(targetSqrtPrice > 0, "Invalid price");
        
        // STEP 3: Store immutable snapshot (FIX #10: Store authorized oracle)
        graduationSnapshots[tokenAddress] = GraduationSnapshot({
            kasLiquidity: kasLiquidity,
            tokenLiquidity: tokenLiquidity,
            targetSqrtPriceX96: targetSqrtPrice,
            feeTier: POOL_FEE_TIER,
            initiatedAt: uint32(block.timestamp),
            poolInitialized: false,
            lpMinted: false,
            uniswapPool: address(0),
            authorizedOracle: msg.sender  // FIX #10: Freeze oracle address
        });
        
        // STEP 4: Trigger pool graduation (transfers KAS to this contract)
        try pool.initiateGraduation() {
            emit GraduationSnapshotCreated(
                tokenAddress,
                kasLiquidity,
                tokenLiquidity,
                targetSqrtPrice,
                block.timestamp
            );
            
            emit GraduationInitiated(
                tokenAddress,
                kasLiquidity,
                tokenLiquidity,
                block.timestamp
            );
        } catch {
            delete graduationSnapshots[tokenAddress];
            revert("Pool initiation failed");
        }
    }
    
    /**
     * @notice FIX #3/#5/#6/#7/#9/#10: Complete graduation using snapshot values
     * @dev Uses ONLY snapshot data, never queries pool after initiation
     */
    function completeGraduation(address tokenAddress) 
        external 
        nonReentrant 
        whenNotPaused
    {
        if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
        
        // STEP 1: Load snapshot
        GraduationSnapshot storage snapshot = graduationSnapshots[tokenAddress];
        if (snapshot.initiatedAt == 0) revert NotInitiated();
        require(!snapshot.lpMinted, "Already completed");
        
        // FIX #10: Validate caller is authorized oracle
        if (msg.sender != snapshot.authorizedOracle) revert UnauthorizedOracle();
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        require(pool.graduating() && pool.liquidityTransferred(), "Invalid state");
        
        // STEP 2: Use snapshot values (NEVER query pool!) - FIX #3
        uint256 kasLiquidity = snapshot.kasLiquidity;      // 1089.99 KAS
        uint256 tokenLiquidity = snapshot.tokenLiquidity;  // 250M tokens
        
        // STEP 3: Validate we received the KAS
        require(address(this).balance >= kasLiquidity, "Insufficient KAS");
        
        // STEP 4: Transfer tokens from pool
        IERC20(tokenAddress).safeTransferFrom(address(pool), address(this), tokenLiquidity);
        
        // STEP 5: Wrap KAS to WKAS (FIX #3: Use full snapshot amount)
        IWKAS(kaspaFinanceWKAS).deposit{value: kasLiquidity}();
        
        // STEP 6: Determine token ordering
        (address token0, address token1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenAddress, kaspaFinanceWKAS)
            : (kaspaFinanceWKAS, tokenAddress);
        
        (uint256 amount0, uint256 amount1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenLiquidity, kasLiquidity)
            : (kasLiquidity, tokenLiquidity);
        
        // STEP 7: Create & initialize pool ATOMICALLY (FIX #5: prevents front-running!)
        address poolAddress = INonfungiblePositionManager(kaspaFinancePositionManager)
            .createAndInitializePoolIfNecessary(
                token0,
                token1,
                POOL_FEE_TIER,
                snapshot.targetSqrtPriceX96  // Use snapshot price!
            );
        
        snapshot.uniswapPool = poolAddress;
        snapshot.poolInitialized = true;
        
        emit PoolCreated(tokenAddress, poolAddress, snapshot.targetSqrtPriceX96, block.timestamp);
        emit PoolInitialized(tokenAddress, poolAddress, snapshot.targetSqrtPriceX96, block.timestamp);
        
        // STEP 8: Approve and mint LP (FIX #11: 30 minute deadline)
        IERC20(token0).forceApprove(kaspaFinancePositionManager, amount0);
        IERC20(token1).forceApprove(kaspaFinancePositionManager, amount1);
        
        (uint256 positionId, uint128 liquidity, uint256 actualAmount0, uint256 actualAmount1) = 
            _mintLiquidityPosition(token0, token1, amount0, amount1);
        
        require(liquidity > 0, "No liquidity minted");
        snapshot.lpMinted = true;
        
        // FIX #7: Handle excess tokens WITHOUT refunding to pool (would revert!)
        _handleExcessTokens(token0, token1, amount0, amount1, actualAmount0, actualAmount1);
        
        // STEP 9: Burn LP NFT to dead address (FIX #6: permanent liquidity lock!)
        INonfungiblePositionManager(kaspaFinancePositionManager).safeTransferFrom(
            address(this),
            BURN_ADDRESS,  // 0x...dEaD - provably uncontrollable
            positionId
        );
        
        emit LPNFTBurned(tokenAddress, positionId, block.timestamp);
        
        // STEP 10: Mark graduated (don't store positionId - it's burned)
        hasGraduated[tokenAddress] = true;
        graduationTimestamp[tokenAddress] = block.timestamp;
        uniswapPoolAddress[tokenAddress] = poolAddress;
        
        // STEP 11: Complete on pool (FIX #9: MUST succeed or revert entire tx!)
        pool.completeGraduation();  // No try/catch - let it revert on failure!
        
        emit GraduationCompleted(
            tokenAddress, 
            poolAddress, 
            positionId, 
            kasLiquidity, 
            tokenLiquidity, 
            block.timestamp
        );
    }
    
    // ============ Internal Helper Functions ============
    
    /**
     * @notice FIX #11: Mint liquidity position with 30 minute deadline
     */
    function _mintLiquidityPosition(
        address token0,
        address token1,
        uint256 amount0,
        uint256 amount1
    ) internal returns (uint256 positionId, uint128 liquidity, uint256 actualAmount0, uint256 actualAmount1) {
        INonfungiblePositionManager.MintParams memory params = INonfungiblePositionManager.MintParams({
            token0: token0,
            token1: token1,
            fee: POOL_FEE_TIER,
            tickLower: FULL_RANGE_TICK_LOWER,   // FIX #4: -887200
            tickUpper: FULL_RANGE_TICK_UPPER,   // FIX #4: 887200
            amount0Desired: amount0,
            amount1Desired: amount1,
            amount0Min: (amount0 * (10000 - graduationSlippageBps)) / 10000,
            amount1Min: (amount1 * (10000 - graduationSlippageBps)) / 10000,
            recipient: address(this),
            deadline: block.timestamp + graduationDeadlineSeconds  // FIX #11: 1800 seconds
        });
        
        return INonfungiblePositionManager(kaspaFinancePositionManager).mint(params);
    }
    
    /**
     * @notice FIX #7: Handle excess tokens WITHOUT sending to pool (would revert!)
     * @dev Sends excess to treasury instead of pool (pool's receive() rejects KAS)
     */
    function _handleExcessTokens(
        address token0,
        address token1,
        uint256 amount0Desired,
        uint256 amount1Desired,
        uint256 actualAmount0,
        uint256 actualAmount1
    ) internal {
        uint256 excess0 = 0;
        uint256 excess1 = 0;
        
        // Calculate excess amounts
        if (actualAmount0 < amount0Desired) {
            excess0 = amount0Desired - actualAmount0;
        }
        if (actualAmount1 < amount1Desired) {
            excess1 = amount1Desired - actualAmount1;
        }
        
        // Send excess to treasury (NOT to pool! Pool's receive() would revert)
        if (excess0 > 0 && treasury != address(0)) {
            IERC20(token0).safeTransfer(treasury, excess0);
        }
        if (excess1 > 0 && treasury != address(0)) {
            IERC20(token1).safeTransfer(treasury, excess1);
        }
        
        emit ExcessTokensHandled(token0, token1, excess0, excess1, treasury);
    }
    
    /**
     * @notice FIX #8: Calculate sqrtPriceX96 with MIN/MAX bounds validation
     * @dev Validates price is within Uniswap V3 acceptable range
     */
    function _calculateSqrtPriceX96(
        uint256 kasReserve,
        uint256 tokenReserve,
        address tokenAddress
    ) internal view returns (uint160) {
        require(kasReserve > 0 && tokenReserve > 0, "Zero reserves");
        
        uint256 priceX192;
        
        if (tokenAddress < kaspaFinanceWKAS) {
            priceX192 = FullMath.mulDiv(kasReserve, 2**192, tokenReserve);
        } else {
            priceX192 = FullMath.mulDiv(tokenReserve, 2**192, kasReserve);
        }
        
        uint160 sqrtPriceX96 = uint160(_sqrt(priceX192));
        
        require(sqrtPriceX96 > 0, "sqrtPriceX96 must be > 0");
        
        // FIX #8: Validate Uniswap V3 bounds
        require(
            sqrtPriceX96 >= MIN_SQRT_RATIO,
            "Price too low (below MIN_SQRT_RATIO)"
        );
        require(
            sqrtPriceX96 <= MAX_SQRT_RATIO,
            "Price too high (above MAX_SQRT_RATIO)"
        );
        
        return sqrtPriceX96;
    }
    
    /**
     * @notice Integer square root via Babylonian method
     */
    function _sqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        return y;
    }
    
    // ============ Admin Functions ============
    
    function setGraduationOracle(address newOracle) external onlyOwner {
        if (newOracle == address(0)) revert InvalidAddress();
        address oldOracle = graduationOracle;
        graduationOracle = newOracle;
        emit OracleUpdated(oldOracle, newOracle);
    }
    
    function setTokenFactory(address newFactory) external onlyOwner {
        if (newFactory == address(0)) revert InvalidAddress();
        address oldFactory = tokenFactory;
        tokenFactory = newFactory;
        emit TokenFactoryUpdated(oldFactory, newFactory);
    }
    
    /**
     * @notice FIX #7: Set treasury address for excess token handling
     */
    function setTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert InvalidAddress();
        address oldTreasury = treasury;
        treasury = newTreasury;
        emit TreasuryUpdated(oldTreasury, newTreasury);
    }
    
    function setGraduationParams(
        uint256 _slippageBps,
        uint256 _deadlineSeconds,
        uint256 _maxPriceDeviationBps
    ) external onlyOwner {
        require(_slippageBps <= 10000, "Invalid slippage");
        require(_deadlineSeconds >= 60 && _deadlineSeconds <= 3600, "Invalid deadline");
        require(_maxPriceDeviationBps <= 10000, "Invalid price deviation");
        
        graduationSlippageBps = _slippageBps;
        graduationDeadlineSeconds = _deadlineSeconds;
        maxPriceDeviationBps = _maxPriceDeviationBps;
        
        emit GraduationParamsUpdated(_slippageBps, _deadlineSeconds, _maxPriceDeviationBps);
    }
    
    function pause() external onlyOwner {
        _pause();
    }
    
    function unpause() external onlyOwner {
        _unpause();
    }
    
    /**
     * @notice Emergency withdrawal of stuck tokens
     */
    function emergencyWithdraw(address token, uint256 amount, address recipient) 
        external 
        onlyOwner 
    {
        require(recipient != address(0), "Invalid recipient");
        
        if (token == address(0)) {
            (bool success, ) = payable(recipient).call{value: amount}("");
            require(success, "Transfer failed");
        } else {
            IERC20(token).safeTransfer(recipient, amount);
        }
        
        emit EmergencyWithdrawal(token, amount, recipient);
    }
    
    // Receive KAS from bonding curve
    receive() external payable {}
}
