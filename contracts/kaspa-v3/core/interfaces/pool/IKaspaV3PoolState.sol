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
