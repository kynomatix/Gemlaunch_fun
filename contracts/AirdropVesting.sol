// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract AirdropVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public constant DAILY_UNLOCK_PCT = 5; // 5% per day
    uint256 public constant VESTING_PERIOD = 20 days;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        
        if (elapsed >= VESTING_PERIOD) {
            return totalAllocation; // 100% unlocked after 20 days
        }
        
        uint256 daysElapsed = elapsed / 1 days;
        uint256 unlocked = (totalAllocation * daysElapsed * DAILY_UNLOCK_PCT) / 100;
        
        return unlocked > totalAllocation ? totalAllocation : unlocked;
    }
    
    function getWithdrawableAmount() public view returns (uint256) {
        uint256 unlocked = getUnlockedAmount();
        return unlocked > withdrawn ? unlocked - withdrawn : 0;
    }
    
    function withdraw() external nonReentrant {
        require(msg.sender == beneficiary, "Only beneficiary can withdraw");
        
        uint256 withdrawable = getWithdrawableAmount();
        require(withdrawable > 0, "No tokens available");
        
        withdrawn += withdrawable;
        
        require(token.transfer(beneficiary, withdrawable), "Transfer failed");
        emit TokensWithdrawn(beneficiary, withdrawable);
    }
}
