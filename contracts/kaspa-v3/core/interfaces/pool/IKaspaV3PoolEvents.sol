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
