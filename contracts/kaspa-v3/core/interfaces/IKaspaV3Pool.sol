// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.5.0;

import './pool/IKaspaV3PoolImmutables.sol';
import './pool/IKaspaV3PoolState.sol';
import './pool/IKaspaV3PoolDerivedState.sol';
import './pool/IKaspaV3PoolActions.sol';
import './pool/IKaspaV3PoolOwnerActions.sol';
import './pool/IKaspaV3PoolEvents.sol';

/// @title The interface for a Kaspa V3 Pool
/// @notice A Kaspa pool facilitates swapping and automated market making between any two assets that strictly conform
/// to the ERC20 specification
/// @dev The pool interface is broken up into many smaller pieces
interface IKaspaV3Pool is
    IKaspaV3PoolImmutables,
    IKaspaV3PoolState,
    IKaspaV3PoolDerivedState,
    IKaspaV3PoolActions,
    IKaspaV3PoolOwnerActions,
    IKaspaV3PoolEvents
{

}
