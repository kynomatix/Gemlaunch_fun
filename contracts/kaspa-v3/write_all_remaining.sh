#!/bin/bash

# Write all pool interface files from earlier fetched data
# IKaspaV3PoolImmutables
cat > core/interfaces/pool/IKaspaV3PoolImmutables.sol <<'POOLIMM'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolImmutables {
    function factory() external view returns (address);
    function token0() external view returns (address);
    function token1() external view returns (address);
    function fee() external view returns (uint24);
    function tickSpacing() external view returns (int24);
    function maxLiquidityPerTick() external view returns (uint128);
}
POOLIMM

# IKaspaV3PoolState
cat > core/interfaces/pool/IKaspaV3PoolState.sol <<'POOLSTATE'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolState {
    function slot0() external view returns (uint160,int24,uint16,uint16,uint16,uint8,bool);
    function feeGrowthGlobal0X128() external view returns (uint256);
    function feeGrowthGlobal1X128() external view returns (uint256);
    function protocolFees() external view returns (uint128,uint128);
    function liquidity() external view returns (uint128);
    function ticks(int24) external view returns (uint128,int128,uint256,uint256,int56,uint160,uint32,bool);
    function tickBitmap(int16) external view returns (uint256);
    function positions(bytes32) external view returns (uint128,uint256,uint256,uint128,uint128);
    function observations(uint256) external view returns (uint32,int56,uint160,bool);
}
POOLSTATE

# IKaspaV3PoolDerivedState
cat > core/interfaces/pool/IKaspaV3PoolDerivedState.sol <<'POOLDERIVED'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolDerivedState {
    function observe(uint32[] calldata) external view returns (int56[] memory,uint160[] memory);
    function snapshotCumulativesInside(int24,int24) external view returns (int56,uint160,uint32);
}
POOLDERIVED

# IKaspaV3PoolActions
cat > core/interfaces/pool/IKaspaV3PoolActions.sol <<'POOLACTIONS'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolActions {
    function initialize(uint160) external;
    function mint(address,int24,int24,uint128,bytes calldata) external returns (uint256,uint256);
    function collect(address,int24,int24,uint128,uint128) external returns (uint128,uint128);
    function burn(int24,int24,uint128) external returns (uint256,uint256);
    function swap(address,bool,int256,uint160,bytes calldata) external returns (int256,int256);
    function flash(address,uint256,uint256,bytes calldata) external;
    function increaseObservationCardinalityNext(uint16) external;
}
POOLACTIONS

# IKaspaV3PoolOwnerActions
cat > core/interfaces/pool/IKaspaV3PoolOwnerActions.sol <<'POOLOWNER'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolOwnerActions {
    function setFeeProtocol(uint8,uint8) external;
    function collectProtocol(address,uint128,uint128) external returns (uint128,uint128);
}
POOLOWNER

# IKaspaV3PoolEvents
cat > core/interfaces/pool/IKaspaV3PoolEvents.sol <<'POOLEVENTS'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolEvents {
    event Initialize(uint160,int24);
    event Mint(address,address indexed,int24 indexed,int24 indexed,uint128,uint256,uint256);
    event Collect(address indexed,address,int24 indexed,int24 indexed,uint128,uint128);
    event Burn(address indexed,int24 indexed,int24 indexed,uint128,uint256,uint256);
    event Swap(address indexed,address indexed,int256,int256,uint160,uint128,int24);
    event Flash(address indexed,address indexed,uint256,uint256,uint256,uint256);
    event IncreaseObservationCardinalityNext(uint16,uint16);
    event SetFeeProtocol(uint8,uint8,uint8,uint8);
    event CollectProtocol(address indexed,address indexed,uint128,uint128);
}
POOLEVENTS

# Periphery interfaces and libraries
cat > periphery/interfaces/IPeripheryImmutableState.sol <<'PERIMM'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IPeripheryImmutableState {
    function factory() external view returns (address);
    function WETH9() external view returns (address);
}
PERIMM

cat > periphery/interfaces/IQuoterV2.sol <<'IQUOTER'
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
IQUOTER

cat > periphery/base/PeripheryImmutableState.sol <<'PERIBASE'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity =0.7.6;
import '../interfaces/IPeripheryImmutableState.sol';
abstract contract PeripheryImmutableState is IPeripheryImmutableState {
    address public immutable override factory;
    address public immutable override WETH9;
    constructor(address _factory, address _WETH9) {
        factory = _factory;
        WETH9 = _WETH9;
    }
}
PERIBASE

cat > periphery/libraries/Path.sol <<'PATH'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.6.0;
import './BytesLib.sol';
library Path {
    using BytesLib for bytes;
    uint256 private constant ADDR_SIZE = 20;
    uint256 private constant FEE_SIZE = 3;
    uint256 private constant NEXT_OFFSET = ADDR_SIZE + FEE_SIZE;
    uint256 private constant POP_OFFSET = NEXT_OFFSET + ADDR_SIZE;
    uint256 private constant MULTIPLE_POOLS_MIN_LENGTH = POP_OFFSET + NEXT_OFFSET;
    function hasMultiplePools(bytes memory path) internal pure returns (bool) { return path.length >= MULTIPLE_POOLS_MIN_LENGTH; }
    function numPools(bytes memory path) internal pure returns (uint256) { return ((path.length - ADDR_SIZE) / NEXT_OFFSET); }
    function decodeFirstPool(bytes memory path) internal pure returns (address,address,uint24) {
        return (path.toAddress(0), path.toAddress(NEXT_OFFSET), path.toUint24(ADDR_SIZE));
    }
    function getFirstPool(bytes memory path) internal pure returns (bytes memory) { return path.slice(0, POP_OFFSET); }
    function skipToken(bytes memory path) internal pure returns (bytes memory) { return path.slice(NEXT_OFFSET, path.length - NEXT_OFFSET); }
}
PATH

cat > periphery/libraries/PoolAddress.sol <<'POOLADDR'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
library PoolAddress {
    bytes32 internal constant POOL_INIT_CODE_HASH = 0xfc0195aaeadd720b52f88b53c0272378fe30a0e86e2b6f2f9ec953b575f5ec5d;
    struct PoolKey { address token0; address token1; uint24 fee; }
    function getPoolKey(address tokenA, address tokenB, uint24 fee) internal pure returns (PoolKey memory) {
        if (tokenA > tokenB) (tokenA, tokenB) = (tokenB, tokenA);
        return PoolKey({token0: tokenA, token1: tokenB, fee: fee});
    }
    function computeAddress(address factory, PoolKey memory key) internal pure returns (address pool) {
        require(key.token0 < key.token1);
        pool = address(uint256(keccak256(abi.encodePacked(hex'ff', factory, keccak256(abi.encode(key.token0, key.token1, key.fee)), POOL_INIT_CODE_HASH))));
    }
}
POOLADDR

cat > periphery/libraries/CallbackValidation.sol <<'CALLBACK'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity =0.7.6;
import 'kaspa-v3-core/contracts/interfaces/IKaspaV3Pool.sol';
import './PoolAddress.sol';
library CallbackValidation {
    function verifyCallback(address factory, address tokenA, address tokenB, uint24 fee) internal view returns (IKaspaV3Pool pool) {
        return verifyCallback(factory, PoolAddress.getPoolKey(tokenA, tokenB, fee));
    }
    function verifyCallback(address factory, PoolAddress.PoolKey memory poolKey) internal view returns (IKaspaV3Pool pool) {
        pool = IKaspaV3Pool(PoolAddress.computeAddress(factory, poolKey));
        require(msg.sender == address(pool));
    }
}
CALLBACK

cat > periphery/libraries/PoolTicksCounter.sol <<'TICKCOUNT'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.6.0;
import 'kaspa-v3-core/contracts/interfaces/IKaspaV3Pool.sol';
library PoolTicksCounter {
    function countInitializedTicksCrossed(IKaspaV3Pool self, int24 tickBefore, int24 tickAfter) internal view returns (uint32 initializedTicksCrossed) {
        int16 wordPosLower; int16 wordPosHigher; uint8 bitPosLower; uint8 bitPosHigher;
        bool tickBeforeInitialized; bool tickAfterInitialized;
        {
            int16 wordPos = int16((tickBefore / self.tickSpacing()) >> 8);
            uint8 bitPos = uint8((tickBefore / self.tickSpacing()) % 256);
            int16 wordPosAfter = int16((tickAfter / self.tickSpacing()) >> 8);
            uint8 bitPosAfter = uint8((tickAfter / self.tickSpacing()) % 256);
            tickAfterInitialized = ((self.tickBitmap(wordPosAfter) & (1 << bitPosAfter)) > 0) && ((tickAfter % self.tickSpacing()) == 0) && (tickBefore > tickAfter);
            tickBeforeInitialized = ((self.tickBitmap(wordPos) & (1 << bitPos)) > 0) && ((tickBefore % self.tickSpacing()) == 0) && (tickBefore < tickAfter);
            if (wordPos < wordPosAfter || (wordPos == wordPosAfter && bitPos <= bitPosAfter)) {
                wordPosLower = wordPos; bitPosLower = bitPos; wordPosHigher = wordPosAfter; bitPosHigher = bitPosAfter;
            } else {
                wordPosLower = wordPosAfter; bitPosLower = bitPosAfter; wordPosHigher = wordPos; bitPosHigher = bitPos;
            }
        }
        uint256 mask = type(uint256).max << bitPosLower;
        while (wordPosLower <= wordPosHigher) {
            if (wordPosLower == wordPosHigher) { mask = mask & (type(uint256).max >> (255 - bitPosHigher)); }
            uint256 masked = self.tickBitmap(wordPosLower) & mask;
            initializedTicksCrossed += countOneBits(masked);
            wordPosLower++; mask = type(uint256).max;
        }
        if (tickAfterInitialized) { initializedTicksCrossed -= 1; }
        if (tickBeforeInitialized) { initializedTicksCrossed -= 1; }
        return initializedTicksCrossed;
    }
    function countOneBits(uint256 x) private pure returns (uint16) {
        uint16 bits = 0;
        while (x != 0) { bits++; x &= (x - 1); }
        return bits;
    }
}
TICKCOUNT

echo "✅ All remaining contract files written successfully!"
