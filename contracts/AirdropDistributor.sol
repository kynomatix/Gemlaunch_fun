// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title AirdropDistributor
 * @notice Helper contract for batch token distributions (airdrops)
 * @dev Transfers tokens from distributor's wallet to multiple recipients atomically
 * 
 * Key Features:
 * - Pre-validates allowance and balance BEFORE loop (fails fast, saves gas)
 * - Atomic execution: all transfers succeed or entire transaction reverts
 * - ReentrancyGuard for security
 * - Emits detailed event for tracking
 * 
 * Usage Flow:
 * 1. Token creator withdraws from vesting contract (if needed)
 * 2. Token creator approves AirdropDistributor for total amount
 * 3. Token creator calls batchTransfer() with recipients and amounts
 */
contract AirdropDistributor is ReentrancyGuard {
    
    /**
     * @notice Emitted when a batch airdrop is successfully distributed
     * @param token The ERC20 token contract address
     * @param distributor The wallet that initiated the distribution
     * @param recipientCount Number of recipients
     * @param totalAmount Total tokens distributed
     */
    event AirdropDistributed(
        address indexed token,
        address indexed distributor,
        uint256 recipientCount,
        uint256 totalAmount
    );
    
    /**
     * @notice Batch transfer tokens to multiple recipients
     * @dev CRITICAL: Pre-validates allowance and balance BEFORE loop to fail fast
     * 
     * @param token The ERC20 token to distribute
     * @param recipients Array of recipient addresses
     * @param amounts Array of token amounts (must match recipients length)
     * 
     * Requirements:
     * - recipients and amounts arrays must have same length
     * - Must have sufficient allowance for this contract
     * - Must have sufficient balance to cover all transfers
     * - All amounts must be > 0
     * - No recipient can be address(0)
     * 
     * Reverts:
     * - "Length mismatch" if arrays don't match
     * - "Empty array" if no recipients
     * - "Invalid amount" if any amount is 0
     * - "Insufficient allowance" if allowance < total
     * - "Insufficient balance" if balance < total
     * - "Invalid recipient" if any recipient is address(0)
     * - "Transfer failed" if any transferFrom fails
     */
    function batchTransfer(
        address token,
        address[] calldata recipients,
        uint256[] calldata amounts
    ) external nonReentrant {
        // Validate array lengths
        require(recipients.length == amounts.length, "Length mismatch");
        require(recipients.length > 0, "Empty array");
        
        IERC20 tokenContract = IERC20(token);
        
        // Step 1: Calculate total amount needed
        uint256 totalAmount = 0;
        for (uint256 i = 0; i < amounts.length; i++) {
            require(amounts[i] > 0, "Invalid amount");
            totalAmount += amounts[i];
        }
        
        // Step 2: Pre-validate allowance (fails fast, not mid-loop)
        uint256 allowance = tokenContract.allowance(msg.sender, address(this));
        require(allowance >= totalAmount, "Insufficient allowance");
        
        // Step 3: Pre-validate balance (fails fast, not mid-loop)
        uint256 balance = tokenContract.balanceOf(msg.sender);
        require(balance >= totalAmount, "Insufficient balance");
        
        // Step 4: Execute transfers (all succeed or entire TX reverts)
        for (uint256 i = 0; i < recipients.length; i++) {
            require(recipients[i] != address(0), "Invalid recipient");
            
            bool success = tokenContract.transferFrom(
                msg.sender,
                recipients[i],
                amounts[i]
            );
            
            require(success, "Transfer failed");
        }
        
        // Emit summary event
        emit AirdropDistributed(
            token,
            msg.sender,
            recipients.length,
            totalAmount
        );
    }
    
    /**
     * @notice Batch transfer equal amounts to all recipients (gas-optimized)
     * @dev Useful when all recipients get the same amount
     * 
     * @param token The ERC20 token to distribute
     * @param recipients Array of recipient addresses
     * @param amountPerRecipient Amount each recipient receives
     */
    function batchTransferEqual(
        address token,
        address[] calldata recipients,
        uint256 amountPerRecipient
    ) external nonReentrant {
        require(recipients.length > 0, "Empty array");
        require(amountPerRecipient > 0, "Invalid amount");
        
        IERC20 tokenContract = IERC20(token);
        
        // Calculate total
        uint256 totalAmount = recipients.length * amountPerRecipient;
        
        // Pre-validate allowance and balance
        require(
            tokenContract.allowance(msg.sender, address(this)) >= totalAmount,
            "Insufficient allowance"
        );
        require(
            tokenContract.balanceOf(msg.sender) >= totalAmount,
            "Insufficient balance"
        );
        
        // Execute transfers
        for (uint256 i = 0; i < recipients.length; i++) {
            require(recipients[i] != address(0), "Invalid recipient");
            
            bool success = tokenContract.transferFrom(
                msg.sender,
                recipients[i],
                amountPerRecipient
            );
            
            require(success, "Transfer failed");
        }
        
        // Emit summary event
        emit AirdropDistributed(
            token,
            msg.sender,
            recipients.length,
            totalAmount
        );
    }
}
