// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./BondingCurvePool.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title PoolMigrationHelper
 * @notice Helper contract to set GraduationController on pools owned by TokenFactory
 * @dev Temporary contract used for testing V4 graduation system
 * 
 * Usage:
 * 1. Deploy this contract (deployer owns it)
 * 2. TokenFactory transfers pool ownership to this contract
 * 3. This contract sets GraduationController on pool
 * 4. This contract transfers pool ownership back to TokenFactory
 */
contract PoolMigrationHelper is Ownable {
    
    event GraduationControllerSet(address indexed pool, address indexed controller);
    event OwnershipTransferred(address indexed pool, address indexed from, address indexed to);
    
    constructor() Ownable(msg.sender) {}
    
    /**
     * @notice Set GraduationController on a pool and transfer ownership back
     * @param poolAddress The pool to migrate
     * @param graduationController The GC address to set
     * @param returnTo Address to return pool ownership to (usually TokenFactory)
     */
    function setGCAndReturn(
        address poolAddress,
        address graduationController,
        address returnTo
    ) external onlyOwner {
        require(poolAddress != address(0), "Bad pool");
        require(graduationController != address(0), "Bad controller");
        require(returnTo != address(0), "Bad return address");
        
        BondingCurvePool pool = BondingCurvePool(payable(poolAddress));
        
        // Verify we own the pool
        require(pool.owner() == address(this), "Pool not owned by helper");
        
        // Set GraduationController
        pool.setGraduationController(graduationController);
        emit GraduationControllerSet(poolAddress, graduationController);
        
        // Transfer ownership back
        pool.transferOwnership(returnTo);
        emit OwnershipTransferred(poolAddress, address(this), returnTo);
    }
    
    /**
     * @notice Emergency function to transfer pool ownership without setting GC
     * @param poolAddress The pool to transfer
     * @param newOwner The new owner
     */
    function emergencyTransfer(address poolAddress, address newOwner) external onlyOwner {
        require(poolAddress != address(0), "Bad pool");
        require(newOwner != address(0), "Bad owner");
        
        BondingCurvePool pool = BondingCurvePool(payable(poolAddress));
        require(pool.owner() == address(this), "Pool not owned by helper");
        
        pool.transferOwnership(newOwner);
        emit OwnershipTransferred(poolAddress, address(this), newOwner);
    }
}
