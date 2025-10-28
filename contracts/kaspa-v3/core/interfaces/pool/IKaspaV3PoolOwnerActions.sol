// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;
interface IKaspaV3PoolOwnerActions {
    function setFeeProtocol(uint8,uint8) external;
    function collectProtocol(address,uint128,uint128) external returns (uint128,uint128);
}
