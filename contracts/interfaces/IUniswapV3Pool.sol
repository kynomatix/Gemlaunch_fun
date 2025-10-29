// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IUniswapV3Pool
 * @notice Interface for Uniswap V3 Pool contract
 * @dev Used by event indexer to listen for Swap events on Kaspa Finance DEX pools
 */
interface IUniswapV3Pool {
    /**
     * @notice Emitted when tokens are swapped in the pool
     * @param sender Address that initiated the swap
     * @param recipient Address that received the output tokens
     * @param amount0 Delta of token0 (negative = sent to pool, positive = received from pool)
     * @param amount1 Delta of token1 (negative = sent to pool, positive = received from pool)
     * @param sqrtPriceX96 The sqrt(price) of the pool after the swap, as a Q64.96
     * @param liquidity The liquidity of the pool after the swap
     * @param tick The log base 1.0001 of price of the pool after the swap
     */
    event Swap(
        address indexed sender,
        address indexed recipient,
        int256 amount0,
        int256 amount1,
        uint160 sqrtPriceX96,
        uint128 liquidity,
        int24 tick
    );
    
    /**
     * @notice The first token of the pool, sorted by address
     * @return The token contract address
     */
    function token0() external view returns (address);
    
    /**
     * @notice The second token of the pool, sorted by address  
     * @return The token contract address
     */
    function token1() external view returns (address);
    
    /**
     * @notice The pool's fee in hundredths of a bip (i.e. 1e-6)
     * @return The fee
     */
    function fee() external view returns (uint24);
    
    /**
     * @notice The currently in-range liquidity available to the pool
     * @return The liquidity at the current price of the pool
     */
    function liquidity() external view returns (uint128);
    
    /**
     * @notice The 0th storage slot in the pool stores many values
     * @return sqrtPriceX96 The current price of the pool as a sqrt(token1/token0) Q64.96 value
     * @return tick The current tick of the pool
     * @return observationIndex The index of the last oracle observation that was written
     * @return observationCardinality The current maximum number of observations stored in the pool
     * @return observationCardinalityNext The next maximum number of observations, to be updated when the observation
     * @return feeProtocol The protocol fee for both tokens of the pool
     * @return unlocked Whether the pool is currently locked to reentrancy
     */
    function slot0()
        external
        view
        returns (
            uint160 sqrtPriceX96,
            int24 tick,
            uint16 observationIndex,
            uint16 observationCardinality,
            uint16 observationCardinalityNext,
            uint8 feeProtocol,
            bool unlocked
        );
}
