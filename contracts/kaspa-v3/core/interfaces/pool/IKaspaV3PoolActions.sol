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
