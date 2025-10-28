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
