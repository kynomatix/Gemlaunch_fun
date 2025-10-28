// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolDerivedState {
    function observe(uint32[] calldata) external view returns (int56[] memory,uint160[] memory);
    function snapshotCumulativesInside(int24,int24) external view returns (int56,uint160,uint32);
}
