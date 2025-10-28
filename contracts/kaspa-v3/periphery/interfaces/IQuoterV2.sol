// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.7.5;
pragma abicoder v2;
interface IQuoterV2 {
    function quoteExactInput(bytes memory,uint256) external returns (uint256,uint160[] memory,uint32[] memory,uint256);
    struct QuoteExactInputSingleParams { address tokenIn; address tokenOut; uint256 amountIn; uint24 fee; uint160 sqrtPriceLimitX96; }
    function quoteExactInputSingle(QuoteExactInputSingleParams memory) external returns (uint256,uint160,uint32,uint256);
    function quoteExactOutput(bytes memory,uint256) external returns (uint256,uint160[] memory,uint32[] memory,uint256);
    struct QuoteExactOutputSingleParams { address tokenIn; address tokenOut; uint256 amount; uint24 fee; uint160 sqrtPriceLimitX96; }
    function quoteExactOutputSingle(QuoteExactOutputSingleParams memory) external returns (uint256,uint160,uint32,uint256);
}
