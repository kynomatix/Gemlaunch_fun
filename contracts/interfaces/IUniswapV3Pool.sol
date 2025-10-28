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
}
