#!/bin/bash

# Fix TickBitmap.sol type conversions for Solidity 0.7.6
cat > core/libraries/TickBitmap.sol << 'TICKBITMAP'
// SPDX-License-Identifier: BUSL-1.1
pragma solidity >=0.5.0;

import './BitMath.sol';

library TickBitmap {
    function position(int24 tick) private pure returns (int16 wordPos, uint8 bitPos) {
        wordPos = int16(tick >> 8);
        bitPos = uint8(uint24(tick) % 256);
    }

    function flipTick(
        mapping(int16 => uint256) storage self,
        int24 tick,
        int24 tickSpacing
    ) internal {
        require(tick % tickSpacing == 0);
        (int16 wordPos, uint8 bitPos) = position(tick / tickSpacing);
        uint256 mask = 1 << bitPos;
        self[wordPos] ^= mask;
    }

    function nextInitializedTickWithinOneWord(
        mapping(int16 => uint256) storage self,
        int24 tick,
        int24 tickSpacing,
        bool lte
    ) internal view returns (int24 next, bool initialized) {
        int24 compressed = tick / tickSpacing;
        if (tick < 0 && tick % tickSpacing != 0) compressed--;

        if (lte) {
            (int16 wordPos, uint8 bitPos) = position(compressed);
            uint256 mask = (1 << bitPos) - 1 + (1 << bitPos);
            uint256 masked = self[wordPos] & mask;
            initialized = masked != 0;
            next = initialized
                ? (compressed - int24(uint24(bitPos) - uint24(BitMath.mostSignificantBit(masked)))) * tickSpacing
                : (compressed - int24(uint24(bitPos))) * tickSpacing;
        } else {
            (int16 wordPos, uint8 bitPos) = position(compressed + 1);
            uint256 mask = ~((1 << bitPos) - 1);
            uint256 masked = self[wordPos] & mask;
            initialized = masked != 0;
            next = initialized
                ? (compressed + 1 + int24(uint24(BitMath.leastSignificantBit(masked)) - uint24(bitPos))) * tickSpacing
                : (compressed + 1 + int24(uint24(type(uint8).max) - uint24(bitPos))) * tickSpacing;
        }
    }
}
TICKBITMAP

# Fix PoolAddress.sol type conversion for Solidity 0.7.6
cat > periphery/libraries/PoolAddress.sol << 'POOLADDR'
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
        pool = address(uint160(uint256(keccak256(abi.encodePacked(hex'ff', factory, keccak256(abi.encode(key.token0, key.token1, key.fee)), POOL_INIT_CODE_HASH)))));
    }
}
POOLADDR

# Fix PoolTicksCounter.sol type conversions for Solidity 0.7.6
cat > periphery/libraries/PoolTicksCounter.sol << 'TICKCOUNT'
// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.6.0;
import '../../core/interfaces/IKaspaV3Pool.sol';
library PoolTicksCounter {
    function countInitializedTicksCrossed(IKaspaV3Pool self, int24 tickBefore, int24 tickAfter) internal view returns (uint32 initializedTicksCrossed) {
        int16 wordPosLower; int16 wordPosHigher; uint8 bitPosLower; uint8 bitPosHigher;
        bool tickBeforeInitialized; bool tickAfterInitialized;
        {
            int16 wordPos = int16((tickBefore / self.tickSpacing()) >> 8);
            uint8 bitPos = uint8(uint24((tickBefore / self.tickSpacing())) % 256);
            int16 wordPosAfter = int16((tickAfter / self.tickSpacing()) >> 8);
            uint8 bitPosAfter = uint8(uint24((tickAfter / self.tickSpacing())) % 256);
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

echo "✅ All type conversion issues fixed for Solidity 0.7.6!"
