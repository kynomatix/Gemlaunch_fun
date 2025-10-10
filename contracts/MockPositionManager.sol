// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockPositionManager {
    uint256 private nextPositionId = 1;

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
    ) {
        tokenId = nextPositionId++;
        liquidity = 1000000;
        amount0 = params.amount0Desired;
        amount1 = params.amount1Desired;
    }
}
