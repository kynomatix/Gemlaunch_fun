// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title GraduationController V2
 * @notice Manages token graduation from bonding curve to Uniswap V3 DEX liquidity
 * @dev Complete rewrite fixing all critical issues from V1:
 *      - Added Uniswap V3 pool creation
 *      - Added pool price initialization
 *      - Fixed token transfer logic
 *      - Added comprehensive validation
 *      - Added security protections
 * 
 * Version: 2.0.0
 * Deployment Date: October 23, 2025
 * Kaspa Finance Integration
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
     * @param a The multiplicand
     * @param b The multiplier
     * @param denominator The divisor
     * @return result The result as a uint256
     */
    function mulDiv(
        uint256 a,
        uint256 b,
        uint256 denominator
    ) internal pure returns (uint256 result) {
        // 512-bit multiply [prod1 prod0] = a * b
        // Compute the product mod 2**256 and mod 2**256 - 1
        // then use the Chinese Remainder Theorem to reconstruct
        uint256 prod0; // Least significant 256 bits of the product
        uint256 prod1; // Most significant 256 bits of the product
        assembly {
            let mm := mulmod(a, b, not(0))
            prod0 := mul(a, b)
            prod1 := sub(sub(mm, prod0), lt(mm, prod0))
        }

        // Handle non-overflow cases, 256 by 256 division
        if (prod1 == 0) {
            require(denominator > 0);
            assembly {
                result := div(prod0, denominator)
            }
            return result;
        }

        // Make sure the result is less than 2**256
        // Also prevents denominator == 0
        require(denominator > prod1);

        ///////////////////////////////////////////////
        // 512 by 256 division.
        ///////////////////////////////////////////////

        // Make division exact by subtracting the remainder from [prod1 prod0]
        // Compute remainder using mulmod
        uint256 remainder;
        assembly {
            remainder := mulmod(a, b, denominator)
        }
        // Subtract 256 bit number from 512 bit number
        assembly {
            prod1 := sub(prod1, gt(remainder, prod0))
            prod0 := sub(prod0, remainder)
        }

        // Factor powers of two out of denominator
        // Compute largest power of two divisor of denominator.
        // Always >= 1.
        uint256 twos = denominator & (~denominator + 1);
        // Divide denominator by power of two
        assembly {
            denominator := div(denominator, twos)
        }

        // Divide [prod1 prod0] by the factors of two
        assembly {
            prod0 := div(prod0, twos)
        }
        // Shift in bits from prod1 into prod0. For this we need
        // to flip `twos` such that it is 2**256 / twos.
        // If twos is zero, then it becomes one
        assembly {
            twos := add(div(sub(0, twos), twos), 1)
        }
        prod0 |= prod1 * twos;

        // Invert denominator mod 2**256
        // Now that denominator is an odd number, it has an inverse
        // modulo 2**256 such that denominator * inv = 1 mod 2**256.
        // Compute the inverse by starting with a seed that is correct
        // correct for four bits. That is, denominator * inv = 1 mod 2**4
        uint256 inv = (3 * denominator) ^ 2;
        // Now use Newton-Raphson iteration to improve the precision.
        // Thanks to Hensel's lifting lemma, this also works in modular
        // arithmetic, doubling the correct bits in each step.
        inv *= 2 - denominator * inv; // inverse mod 2**8
        inv *= 2 - denominator * inv; // inverse mod 2**16
        inv *= 2 - denominator * inv; // inverse mod 2**32
        inv *= 2 - denominator * inv; // inverse mod 2**64
        inv *= 2 - denominator * inv; // inverse mod 2**128
        inv *= 2 - denominator * inv; // inverse mod 2**256

        // Because the division is now exact we can divide by multiplying
        // with the modular inverse of denominator. This will give us the
        // correct result modulo 2**256. Since the preconditions guarantee
        // that the outcome is less than 2**256, this is the final result.
        // We don't need to compute the high bits of the result and prod1
        // is no longer required.
        result = prod0 * inv;
        return result;
    }
}

/**
 * @title Uniswap V3 Factory Interface
 * @notice Interface for creating and querying Uniswap V3 pools
 */
interface IUniswapV3Factory {
    /**
     * @notice Creates a new Uniswap V3 pool for the given token pair and fee tier
     * @param tokenA First token address
     * @param tokenB Second token address
     * @param fee Fee tier (500 = 0.05%, 2500 = 0.25%, 3000 = 0.30%, 10000 = 1%)
     * @return pool Address of the created pool
     */
    function createPool(address tokenA, address tokenB, uint24 fee) 
        external returns (address pool);
    
    /**
     * @notice Returns the pool address for a given token pair and fee tier
     * @param tokenA First token address
     * @param tokenB Second token address
     * @param fee Fee tier
     * @return pool Address of the pool (address(0) if doesn't exist)
     */
    function getPool(address tokenA, address tokenB, uint24 fee) 
        external view returns (address pool);
}

/**
 * @title Uniswap V3 Pool Interface
 * @notice Interface for initializing and querying Uniswap V3 pool state
 */
interface IUniswapV3Pool {
    /**
     * @notice Initialize the pool with a starting price
     * @dev Can only be called once. Must be called before any liquidity operations
     * @param sqrtPriceX96 The initial sqrt price of the pool as a Q64.96 value
     */
    function initialize(uint160 sqrtPriceX96) external;
    
    /**
     * @notice Returns the current state of the pool
     * @return sqrtPriceX96 The current price of the pool as a sqrt(token1/token0) Q64.96 value
     * @return tick The current tick of the pool
     * @return observationIndex The index of the last oracle observation
     * @return observationCardinality The current maximum number of observations stored
     * @return observationCardinalityNext The next maximum number of observations to store
     * @return feeProtocol The protocol fee for both tokens of the pool
     * @return unlocked Whether the pool is currently locked to reentrancy
     */
    function slot0() external view returns (
        uint160 sqrtPriceX96,
        int24 tick,
        uint16 observationIndex,
        uint16 observationCardinality,
        uint16 observationCardinalityNext,
        uint8 feeProtocol,
        bool unlocked
    );
    
    /**
     * @notice Returns the first token of the pool (lower address)
     */
    function token0() external view returns (address);
    
    /**
     * @notice Returns the second token of the pool (higher address)
     */
    function token1() external view returns (address);
}

/**
 * @title Uniswap V3 NFT Position Manager Interface
 * @notice Interface for managing Uniswap V3 liquidity positions as NFTs
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
    
    /**
     * @notice Mint a new liquidity position NFT
     * @param params Parameters for minting the position
     * @return tokenId The ID of the newly minted NFT
     * @return liquidity The amount of liquidity minted
     * @return amount0 The amount of token0 added
     * @return amount1 The amount of token1 added
     */
    function mint(MintParams calldata params) external payable returns (
        uint256 tokenId,
        uint128 liquidity,
        uint256 amount0,
        uint256 amount1
    );
    
    /**
     * @notice Collect fees from a position
     * @param params Parameters for collecting fees
     * @return amount0 The amount of token0 fees collected
     * @return amount1 The amount of token1 fees collected
     */
    function collect(CollectParams calldata params) external payable returns (
        uint256 amount0,
        uint256 amount1
    );
}

/**
 * @title Wrapped KAS Interface
 * @notice Interface for wrapping and unwrapping KAS
 */
interface IWKAS {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title GraduationController V2
 * @notice Main graduation controller with complete Uniswap V3 integration
 */
contract GraduationController is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;
    
    // ============ State Variables ============
    
    /// @notice Contract version for tracking deployments
    string public constant VERSION = "2.0.0";
    
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
    
    // Graduation tracking
    mapping(address => bool) public hasGraduated;
    mapping(address => uint256) public graduationTimestamp;
    mapping(address => uint256) public liquidityPositionId;
    mapping(address => address) public uniswapPoolAddress;
    
    // Expected liquidity amounts (stored during initiation)
    mapping(address => uint256) public expectedKasLiquidity;
    mapping(address => uint256) public expectedTokenLiquidity;
    
    // ============ Constants ============
    
    /// @notice Uniswap V3 pool fee tier (0.25%)
    uint24 public constant POOL_FEE_TIER = 2500;
    
    /// @notice Full range liquidity position tick bounds
    int24 public constant FULL_RANGE_TICK_LOWER = -887220;
    int24 public constant FULL_RANGE_TICK_UPPER = 887220;
    
    /// @notice Initial virtual KAS reserve in bonding curve
    uint256 public constant INITIAL_VIRTUAL_KAS = 1000 ether;
    
    /// @notice Percentage of token supply to add as liquidity (25%)
    uint256 public constant LP_SUPPLY_PERCENTAGE = 25;
    
    // ============ Configurable Parameters ============
    
    /// @notice Slippage tolerance for liquidity minting (in basis points, 500 = 5%)
    uint256 public graduationSlippageBps = 500;
    
    /// @notice Deadline for graduation transactions (in seconds)
    uint256 public graduationDeadlineSeconds = 300;
    
    /// @notice Maximum price deviation tolerance (in basis points, 100 = 1%)
    uint256 public maxPriceDeviationBps = 100;
    
    // ============ Events ============
    
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
    event GraduationParamsUpdated(uint256 slippageBps, uint256 deadlineSeconds, uint256 maxPriceDeviationBps);
    event EmergencyWithdrawal(address indexed token, uint256 amount, address indexed recipient);
    
    // ============ Errors ============
    
    error OnlyOracle();
    error OnlyValidToken();
    error AlreadyGraduated();
    error NotGraduating();
    error LiquidityNotTransferred();
    error InsufficientKAS();
    error InsufficientTokens();
    error InvalidPoolAddress();
    error InvalidPrice();
    error PriceDeviationTooHigh();
    error SlippageExceeded();
    error NoLiquidityMinted();
    error InvalidAddress();
    error InvalidParameters();
    error PoolCreationFailed();
    error PoolInitializationFailed();
    error TransferFailed();
    
    // ============ Constructor ============
    
    /**
     * @notice Initialize the GraduationController with Kaspa Finance addresses
     * @param _kaspaFinanceFactory Uniswap V3 factory address
     * @param _kaspaFinancePositionManager NFT Position Manager address
     * @param _kaspaFinanceWKAS Wrapped KAS token address
     * @param _graduationOracle Backend oracle address authorized to trigger graduations
     * @param _tokenFactory TokenFactory address for validating tokens
     */
    constructor(
        address _kaspaFinanceFactory,
        address _kaspaFinancePositionManager,
        address _kaspaFinanceWKAS,
        address _graduationOracle,
        address _tokenFactory
    ) Ownable(msg.sender) {
        if (_kaspaFinanceFactory == address(0)) revert InvalidAddress();
        if (_kaspaFinancePositionManager == address(0)) revert InvalidAddress();
        if (_kaspaFinanceWKAS == address(0)) revert InvalidAddress();
        if (_graduationOracle == address(0)) revert InvalidAddress();
        if (_tokenFactory == address(0)) revert InvalidAddress();
        
        // Validate no duplicate addresses
        require(
            _kaspaFinanceFactory != _kaspaFinancePositionManager &&
            _kaspaFinanceFactory != _kaspaFinanceWKAS &&
            _kaspaFinancePositionManager != _kaspaFinanceWKAS,
            "Duplicate addresses"
        );
        
        kaspaFinanceFactory = _kaspaFinanceFactory;
        kaspaFinancePositionManager = _kaspaFinancePositionManager;
        kaspaFinanceWKAS = _kaspaFinanceWKAS;
        graduationOracle = _graduationOracle;
        tokenFactory = _tokenFactory;
    }
    
    // ============ Modifiers ============
    
    /**
     * @notice Ensure caller is the authorized graduation oracle
     */
    modifier onlyOracle() {
        if (msg.sender != graduationOracle) revert OnlyOracle();
        _;
    }
    
    /**
     * @notice Ensure token address is a valid BondingCurvePool from our factory
     * @param tokenAddress The token address to validate
     */
    modifier onlyValidToken(address tokenAddress) {
        // This assumes TokenFactory has a mapping: mapping(address => bool) public isValidToken;
        // If not, we can use a try-catch pattern or maintain our own registry
        if (tokenFactory != address(0)) {
            (bool success, bytes memory data) = tokenFactory.staticcall(
                abi.encodeWithSignature("isValidToken(address)", tokenAddress)
            );
            if (success && data.length > 0) {
                bool isValid = abi.decode(data, (bool));
                if (!isValid) revert OnlyValidToken();
            }
        }
        _;
    }
    
    // ============ Receive Function ============
    
    /**
     * @notice Allow contract to receive KAS for graduation liquidity
     */
    receive() external payable {}
    
    // ============ Main Graduation Functions ============
    
    /**
     * @notice Step 1: Initiate graduation process
     * @dev Called by backend oracle when token reaches $50 market cap
     * @param tokenAddress Address of the BondingCurvePool token to graduate
     */
    function initiateGraduation(address tokenAddress) 
        external 
        nonReentrant 
        whenNotPaused
        onlyOracle 
        onlyValidToken(tokenAddress)
    {
        if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        
        // Calculate expected liquidity amounts BEFORE initiating
        uint256 expectedKas = pool.virtualKasReserve() > INITIAL_VIRTUAL_KAS 
            ? pool.virtualKasReserve() - INITIAL_VIRTUAL_KAS 
            : 0;
        uint256 expectedTokens = (pool.totalSupply() * LP_SUPPLY_PERCENTAGE) / 100;
        
        if (expectedKas == 0 || expectedTokens == 0) revert InsufficientKAS();
        
        // Store expected amounts
        expectedKasLiquidity[tokenAddress] = expectedKas;
        expectedTokenLiquidity[tokenAddress] = expectedTokens;
        
        // Trigger graduation on the pool contract
        // This should transfer KAS to this contract and set graduating = true
        try pool.initiateGraduation() {
            emit GraduationInitiated(
                tokenAddress,
                expectedKas,
                expectedTokens,
                block.timestamp
            );
        } catch Error(string memory reason) {
            emit GraduationFailed(tokenAddress, reason, block.timestamp);
            revert(reason);
        } catch (bytes memory) {
            emit GraduationFailed(tokenAddress, "Unknown error in pool.initiateGraduation", block.timestamp);
            revert("Pool graduation initiation failed");
        }
    }
    
    /**
     * @notice Step 2: Complete graduation by creating Uniswap V3 pool and adding liquidity
     * @dev Called by backend oracle after initiation succeeds
     * @param tokenAddress Address of the BondingCurvePool token to graduate
     */
    function completeGraduation(address tokenAddress) 
        external 
        nonReentrant 
        whenNotPaused
        onlyOracle 
    {
        if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        
        // Validate pool state
        if (!pool.graduating()) revert NotGraduating();
        if (!pool.liquidityTransferred()) revert LiquidityNotTransferred();
        
        // Get expected liquidity amounts
        uint256 kasLiquidity = expectedKasLiquidity[tokenAddress];
        uint256 tokenLiquidity = expectedTokenLiquidity[tokenAddress];
        
        if (kasLiquidity == 0 || tokenLiquidity == 0) revert InsufficientKAS();
        
        // Validate we actually received the KAS
        if (address(this).balance < kasLiquidity) revert InsufficientKAS();
        
        // Validate we have token approval or balance
        uint256 tokenBalance = IERC20(tokenAddress).balanceOf(address(this));
        uint256 tokenAllowance = IERC20(tokenAddress).allowance(address(pool), address(this));
        
        if (tokenBalance < tokenLiquidity && tokenAllowance < tokenLiquidity) {
            revert InsufficientTokens();
        }
        
        // Transfer tokens if we don't already have them
        if (tokenBalance < tokenLiquidity) {
            IERC20(tokenAddress).safeTransferFrom(address(pool), address(this), tokenLiquidity);
        }
        
        // Wrap KAS to WKAS
        IWKAS wkas = IWKAS(kaspaFinanceWKAS);
        wkas.deposit{value: kasLiquidity}();
        
        // Determine token ordering (Uniswap V3 requires token0 < token1)
        (address token0, address token1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenAddress, kaspaFinanceWKAS)
            : (kaspaFinanceWKAS, tokenAddress);
        
        (uint256 amount0, uint256 amount1) = tokenAddress < kaspaFinanceWKAS
            ? (tokenLiquidity, kasLiquidity)
            : (kasLiquidity, tokenLiquidity);
        
        // Create or get Uniswap V3 pool
        address poolAddress = _getOrCreatePool(token0, token1);
        
        // Initialize pool price if needed
        _initializePoolIfNeeded(poolAddress, pool, tokenAddress);
        
        // Approve position manager to spend tokens
        IERC20(token0).safeApprove(kaspaFinancePositionManager, amount0);
        IERC20(token1).safeApprove(kaspaFinancePositionManager, amount1);
        
        // Mint full-range liquidity position
        (uint256 positionId, uint128 liquidity, uint256 actualAmount0, uint256 actualAmount1) = 
            _mintLiquidityPosition(token0, token1, amount0, amount1);
        
        // Validate liquidity was actually minted
        if (liquidity == 0) revert NoLiquidityMinted();
        
        // Validate actual amounts meet minimum requirements
        uint256 minAmount0 = (amount0 * (10000 - graduationSlippageBps)) / 10000;
        uint256 minAmount1 = (amount1 * (10000 - graduationSlippageBps)) / 10000;
        if (actualAmount0 < minAmount0 || actualAmount1 < minAmount1) {
            revert SlippageExceeded();
        }
        
        // Refund any excess tokens back to the pool
        _refundExcessTokens(token0, token1, amount0, amount1, actualAmount0, actualAmount1, address(pool));
        
        // Update state
        hasGraduated[tokenAddress] = true;
        graduationTimestamp[tokenAddress] = block.timestamp;
        liquidityPositionId[tokenAddress] = positionId;
        uniswapPoolAddress[tokenAddress] = poolAddress;
        
        // Clear expected liquidity storage to save gas
        delete expectedKasLiquidity[tokenAddress];
        delete expectedTokenLiquidity[tokenAddress];
        
        // Complete graduation on pool contract (sets graduated = true, burns unsold tokens)
        try pool.completeGraduation() {
            // Success
        } catch Error(string memory reason) {
            // Log but don't revert - liquidity is already added
            emit GraduationFailed(tokenAddress, string(abi.encodePacked("Pool completion failed: ", reason)), block.timestamp);
        }
        
        // Determine which amount is KAS vs Token for event
        uint256 kasAdded = (token1 == kaspaFinanceWKAS) ? actualAmount1 : actualAmount0;
        uint256 tokensAdded = (token0 == tokenAddress) ? actualAmount0 : actualAmount1;
        
        emit GraduationCompleted(
            tokenAddress,
            poolAddress,
            positionId,
            kasAdded,
            tokensAdded,
            block.timestamp
        );
    }
    
    // ============ Internal Helper Functions ============
    
    /**
     * @notice Create Uniswap V3 pool or return existing pool address
     * @param token0 First token address (must be < token1)
     * @param token1 Second token address (must be > token0)
     * @return poolAddress Address of the Uniswap V3 pool
     */
    function _getOrCreatePool(address token0, address token1) 
        internal 
        returns (address poolAddress) 
    {
        IUniswapV3Factory factory = IUniswapV3Factory(kaspaFinanceFactory);
        
        // Check if pool already exists
        poolAddress = factory.getPool(token0, token1, POOL_FEE_TIER);
        
        if (poolAddress == address(0)) {
            // Pool doesn't exist, create it
            poolAddress = factory.createPool(token0, token1, POOL_FEE_TIER);
            
            if (poolAddress == address(0)) revert PoolCreationFailed();
            
            emit PoolCreated(token0, poolAddress, 0, block.timestamp);
        }
        
        return poolAddress;
    }
    
    /**
     * @notice Initialize Uniswap V3 pool with correct starting price if not already initialized
     * @param poolAddress Address of the Uniswap V3 pool
     * @param pool Reference to the BondingCurvePool contract
     * @param tokenAddress Address of the token being graduated
     */
    function _initializePoolIfNeeded(
        address poolAddress, 
        BondingCurvePool pool,
        address tokenAddress
    ) internal {
        IUniswapV3Pool uniPool = IUniswapV3Pool(poolAddress);
        
        // Check if pool is already initialized
        (uint160 sqrtPriceX96, , , , , , ) = uniPool.slot0();
        
        if (sqrtPriceX96 == 0) {
            // Pool not initialized, calculate and set initial price
            uint160 initialSqrtPrice = _calculateSqrtPriceX96(
                pool.virtualKasReserve(),
                pool.virtualTokenReserve(),
                tokenAddress
            );
            
            if (initialSqrtPrice == 0) revert InvalidPrice();
            
            try uniPool.initialize(initialSqrtPrice) {
                emit PoolInitialized(tokenAddress, poolAddress, initialSqrtPrice, block.timestamp);
            } catch {
                revert PoolInitializationFailed();
            }
        } else {
            // Pool already initialized, validate price is reasonable
            uint160 expectedSqrtPrice = _calculateSqrtPriceX96(
                pool.virtualKasReserve(),
                pool.virtualTokenReserve(),
                tokenAddress
            );
            
            _validatePriceDeviation(sqrtPriceX96, expectedSqrtPrice);
        }
    }
    
    /**
     * @notice Calculate sqrtPriceX96 for pool initialization
     * @dev Uniswap V3 requires sqrtPriceX96 = sqrt(price) * 2^96 as a Q64.96 fixed point number
     *      Uses FullMath.mulDiv to safely calculate (reserve * 2^192 / reserve) without overflow
     *      This is critical because shifting reserves by 192 would overflow uint256
     * @param kasReserve Virtual KAS reserve from bonding curve
     * @param tokenReserve Virtual token reserve from bonding curve
     * @param tokenAddress Address of the token being graduated
     * @return sqrtPriceX96 The sqrt price as a Q64.96 fixed point number
     */
    function _calculateSqrtPriceX96(
        uint256 kasReserve,
        uint256 tokenReserve,
        address tokenAddress
    ) internal view returns (uint160) {
        require(kasReserve > 0 && tokenReserve > 0, "Invalid reserves");
        
        // Determine token ordering
        bool tokenIsToken0 = tokenAddress < kaspaFinanceWKAS;
        
        // Calculate price * 2^192 using safe 512-bit multiplication
        // Uniswap V3 price = token1/token0 (where token0 < token1)
        // We need: sqrt(price * 2^192) = sqrt(price) * 2^96
        //
        // CRITICAL FIX: Use FullMath.mulDiv instead of shift to prevent overflow
        // For real reserves like 1131 KAS (10^21 wei), shifting by 192 would overflow uint256
        
        uint256 priceX192;
        if (tokenIsToken0) {
            // token0 = token, token1 = WKAS
            // price = WKAS/token = kasReserve/tokenReserve
            // priceX192 = kasReserve * 2^192 / tokenReserve
            priceX192 = FullMath.mulDiv(kasReserve, uint256(1) << 192, tokenReserve);
        } else {
            // token0 = WKAS, token1 = token
            // price = token/WKAS = tokenReserve/kasReserve
            // priceX192 = tokenReserve * 2^192 / kasReserve
            priceX192 = FullMath.mulDiv(tokenReserve, uint256(1) << 192, kasReserve);
        }
        
        // Calculate sqrt(priceX192) = sqrt(price * 2^192) = sqrt(price) * 2^96
        uint160 sqrtPriceX96 = uint160(_sqrt(priceX192));
        
        require(sqrtPriceX96 > 0, "sqrtPriceX96 must be > 0");
        
        return sqrtPriceX96;
    }
    
    /**
     * @notice Calculate square root using Babylonian method
     * @dev Used for calculating sqrtPriceX96
     * @param x Input value
     * @return y Square root of x
     */
    function _sqrt(uint256 x) internal pure returns (uint256 y) {
        if (x == 0) return 0;
        
        uint256 z = (x + 1) / 2;
        y = x;
        
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }
    
    /**
     * @notice Validate that actual pool price doesn't deviate too much from expected
     * @param actualSqrtPrice Actual sqrt price from the pool
     * @param expectedSqrtPrice Expected sqrt price based on bonding curve
     */
    function _validatePriceDeviation(uint160 actualSqrtPrice, uint160 expectedSqrtPrice) 
        internal 
        view 
    {
        uint256 deviation;
        if (actualSqrtPrice > expectedSqrtPrice) {
            deviation = actualSqrtPrice - expectedSqrtPrice;
        } else {
            deviation = expectedSqrtPrice - actualSqrtPrice;
        }
        
        uint256 maxDeviation = (uint256(expectedSqrtPrice) * maxPriceDeviationBps) / 10000;
        
        if (deviation > maxDeviation) revert PriceDeviationTooHigh();
    }
    
    /**
     * @notice Mint a full-range liquidity position on Uniswap V3
     * @param token0 First token address
     * @param token1 Second token address
     * @param amount0 Amount of token0 to add
     * @param amount1 Amount of token1 to add
     * @return tokenId NFT position ID
     * @return liquidity Amount of liquidity minted
     * @return actualAmount0 Actual amount of token0 added
     * @return actualAmount1 Actual amount of token1 added
     */
    function _mintLiquidityPosition(
        address token0,
        address token1,
        uint256 amount0,
        uint256 amount1
    ) internal returns (
        uint256 tokenId,
        uint128 liquidity,
        uint256 actualAmount0,
        uint256 actualAmount1
    ) {
        INonfungiblePositionManager.MintParams memory params = INonfungiblePositionManager.MintParams({
            token0: token0,
            token1: token1,
            fee: POOL_FEE_TIER,
            tickLower: FULL_RANGE_TICK_LOWER,
            tickUpper: FULL_RANGE_TICK_UPPER,
            amount0Desired: amount0,
            amount1Desired: amount1,
            amount0Min: (amount0 * (10000 - graduationSlippageBps)) / 10000,
            amount1Min: (amount1 * (10000 - graduationSlippageBps)) / 10000,
            recipient: address(this),
            deadline: block.timestamp + graduationDeadlineSeconds
        });
        
        return INonfungiblePositionManager(kaspaFinancePositionManager).mint(params);
    }
    
    /**
     * @notice Refund excess tokens that weren't used in liquidity minting
     * @param token0 First token address
     * @param token1 Second token address
     * @param amount0Desired Desired amount of token0
     * @param amount1Desired Desired amount of token1
     * @param actualAmount0 Actual amount of token0 used
     * @param actualAmount1 Actual amount of token1 used
     * @param recipient Address to receive refunded tokens (usually the pool)
     */
    function _refundExcessTokens(
        address token0,
        address token1,
        uint256 amount0Desired,
        uint256 amount1Desired,
        uint256 actualAmount0,
        uint256 actualAmount1,
        address recipient
    ) internal {
        // Refund excess token0
        if (actualAmount0 < amount0Desired) {
            uint256 excess0 = amount0Desired - actualAmount0;
            if (excess0 > 0) {
                if (token0 == kaspaFinanceWKAS) {
                    // Unwrap WKAS and send KAS
                    IWKAS(kaspaFinanceWKAS).withdraw(excess0);
                    (bool success, ) = recipient.call{value: excess0}("");
                    if (!success) revert TransferFailed();
                } else {
                    // Transfer token
                    IERC20(token0).safeTransfer(recipient, excess0);
                }
            }
        }
        
        // Refund excess token1
        if (actualAmount1 < amount1Desired) {
            uint256 excess1 = amount1Desired - actualAmount1;
            if (excess1 > 0) {
                if (token1 == kaspaFinanceWKAS) {
                    // Unwrap WKAS and send KAS
                    IWKAS(kaspaFinanceWKAS).withdraw(excess1);
                    (bool success, ) = recipient.call{value: excess1}("");
                    if (!success) revert TransferFailed();
                } else {
                    // Transfer token
                    IERC20(token1).safeTransfer(recipient, excess1);
                }
            }
        }
    }
    
    // ============ Liquidity Management Functions ============
    
    /**
     * @notice Collect trading fees from a graduated token's liquidity position
     * @dev Only owner can collect fees (could be DAO in future)
     * @param tokenAddress Address of the graduated token
     * @return amount0 Amount of token0 fees collected
     * @return amount1 Amount of token1 fees collected
     */
    function collectFees(address tokenAddress) 
        external 
        nonReentrant
        onlyOwner 
        returns (uint256 amount0, uint256 amount1) 
    {
        if (!hasGraduated[tokenAddress]) revert NotGraduating();
        
        uint256 tokenId = liquidityPositionId[tokenAddress];
        require(tokenId > 0, "No position");
        
        INonfungiblePositionManager.CollectParams memory params = INonfungiblePositionManager.CollectParams({
            tokenId: tokenId,
            recipient: owner(),
            amount0Max: type(uint128).max,
            amount1Max: type(uint128).max
        });
        
        (amount0, amount1) = INonfungiblePositionManager(kaspaFinancePositionManager).collect(params);
        
        emit FeesCollected(tokenAddress, amount0, amount1, block.timestamp);
    }
    
    // ============ Emergency & Admin Functions ============
    
    /**
     * @notice Cancel a failed graduation and return funds to pool
     * @dev Only owner can cancel graduations
     * @param tokenAddress Address of the token with failed graduation
     */
    function cancelGraduation(address tokenAddress) 
        external 
        nonReentrant
        onlyOwner 
    {
        if (hasGraduated[tokenAddress]) revert AlreadyGraduated();
        
        BondingCurvePool pool = BondingCurvePool(payable(tokenAddress));
        if (!pool.graduating()) revert NotGraduating();
        
        // Get expected amounts
        uint256 kasToReturn = expectedKasLiquidity[tokenAddress];
        uint256 tokensToReturn = expectedTokenLiquidity[tokenAddress];
        
        // Return KAS to pool if we have it
        if (kasToReturn > 0 && address(this).balance >= kasToReturn) {
            (bool success, ) = address(pool).call{value: kasToReturn}("");
            require(success, "KAS return failed");
        }
        
        // Return tokens to pool if we have them
        uint256 tokenBalance = IERC20(tokenAddress).balanceOf(address(this));
        if (tokenBalance > 0) {
            IERC20(tokenAddress).safeTransfer(address(pool), tokenBalance);
        }
        
        // Clear expected liquidity
        delete expectedKasLiquidity[tokenAddress];
        delete expectedTokenLiquidity[tokenAddress];
        
        // Try to revert pool state (requires pool to implement this)
        try pool.cancelGraduation() {
            // Success
        } catch {
            // Pool doesn't support cancellation, continue anyway
        }
        
        emit GraduationCancelled(
            tokenAddress, 
            kasToReturn, 
            tokensToReturn,
            "Cancelled by admin",
            block.timestamp
        );
    }
    
    /**
     * @notice Emergency withdraw accidentally sent tokens
     * @dev Cannot withdraw graduated tokens or WKAS
     * @param token Token address to withdraw
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(address token, uint256 amount) 
        external 
        onlyOwner 
    {
        require(!hasGraduated[token], "Cannot withdraw graduated token");
        require(token != kaspaFinanceWKAS, "Cannot withdraw WKAS directly");
        
        IERC20(token).safeTransfer(owner(), amount);
        
        emit EmergencyWithdrawal(token, amount, owner());
    }
    
    /**
     * @notice Emergency withdraw KAS
     * @dev Use with caution - should only be for stuck funds
     */
    function emergencyWithdrawKAS() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No KAS to withdraw");
        
        (bool success, ) = owner().call{value: balance}("");
        require(success, "KAS withdrawal failed");
        
        emit EmergencyWithdrawal(address(0), balance, owner());
    }
    
    /**
     * @notice Pause all graduations in case of emergency
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @notice Unpause graduations
     */
    function unpause() external onlyOwner {
        _unpause();
    }
    
    // ============ Configuration Functions ============
    
    /**
     * @notice Update the graduation oracle address
     * @param newOracle New oracle address
     */
    function setGraduationOracle(address newOracle) external onlyOwner {
        if (newOracle == address(0)) revert InvalidAddress();
        
        address oldOracle = graduationOracle;
        graduationOracle = newOracle;
        
        emit OracleUpdated(oldOracle, newOracle);
    }
    
    /**
     * @notice Update the token factory address
     * @param newFactory New token factory address
     */
    function setTokenFactory(address newFactory) external onlyOwner {
        if (newFactory == address(0)) revert InvalidAddress();
        
        address oldFactory = tokenFactory;
        tokenFactory = newFactory;
        
        emit TokenFactoryUpdated(oldFactory, newFactory);
    }
    
    /**
     * @notice Update graduation parameters
     * @param _slippageBps Slippage tolerance in basis points (50-1000 = 0.5%-10%)
     * @param _deadlineSeconds Transaction deadline in seconds (60-3600 = 1min-1hour)
     * @param _maxPriceDeviationBps Maximum price deviation in basis points (10-500 = 0.1%-5%)
     */
    function setGraduationParams(
        uint256 _slippageBps, 
        uint256 _deadlineSeconds,
        uint256 _maxPriceDeviationBps
    ) external onlyOwner {
        if (_slippageBps < 50 || _slippageBps > 1000) revert InvalidParameters();
        if (_deadlineSeconds < 60 || _deadlineSeconds > 3600) revert InvalidParameters();
        if (_maxPriceDeviationBps < 10 || _maxPriceDeviationBps > 500) revert InvalidParameters();
        
        graduationSlippageBps = _slippageBps;
        graduationDeadlineSeconds = _deadlineSeconds;
        maxPriceDeviationBps = _maxPriceDeviationBps;
        
        emit GraduationParamsUpdated(_slippageBps, _deadlineSeconds, _maxPriceDeviationBps);
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Check if a token has graduated
     * @param tokenAddress Token address to check
     * @return Whether the token has graduated
     */
    function isGraduated(address tokenAddress) external view returns (bool) {
        return hasGraduated[tokenAddress];
    }
    
    /**
     * @notice Get detailed graduation information for a token
     * @param tokenAddress Token address to query
     * @return graduated Whether token has graduated
     * @return timestamp When graduation completed
     * @return positionId Uniswap V3 NFT position ID
     * @return poolAddress Uniswap V3 pool address
     */
    function getGraduationInfo(address tokenAddress) 
        external 
        view 
        returns (
            bool graduated,
            uint256 timestamp,
            uint256 positionId,
            address poolAddress
        ) 
    {
        return (
            hasGraduated[tokenAddress],
            graduationTimestamp[tokenAddress],
            liquidityPositionId[tokenAddress],
            uniswapPoolAddress[tokenAddress]
        );
    }
    
    /**
     * @notice Get graduation information for multiple tokens
     * @param tokens Array of token addresses
     * @return graduated Array of graduation statuses
     * @return timestamps Array of graduation timestamps
     * @return positionIds Array of position IDs
     * @return poolAddresses Array of pool addresses
     */
    function getMultipleGraduationInfo(address[] calldata tokens)
        external
        view
        returns (
            bool[] memory graduated,
            uint256[] memory timestamps,
            uint256[] memory positionIds,
            address[] memory poolAddresses
        )
    {
        uint256 length = tokens.length;
        graduated = new bool[](length);
        timestamps = new uint256[](length);
        positionIds = new uint256[](length);
        poolAddresses = new address[](length);
        
        for (uint256 i = 0; i < length; i++) {
            graduated[i] = hasGraduated[tokens[i]];
            timestamps[i] = graduationTimestamp[tokens[i]];
            positionIds[i] = liquidityPositionId[tokens[i]];
            poolAddresses[i] = uniswapPoolAddress[tokens[i]];
        }
    }
    
    /**
     * @notice Get expected liquidity amounts for a token in graduation process
     * @param tokenAddress Token address
     * @return expectedKas Expected KAS liquidity
     * @return expectedTokens Expected token liquidity
     */
    function getExpectedLiquidity(address tokenAddress)
        external
        view
        returns (uint256 expectedKas, uint256 expectedTokens)
    {
        return (
            expectedKasLiquidity[tokenAddress],
            expectedTokenLiquidity[tokenAddress]
        );
    }
}
