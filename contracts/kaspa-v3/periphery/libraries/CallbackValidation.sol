// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity =0.7.6;
import '../../core/interfaces/IKaspaV3Pool.sol';
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
