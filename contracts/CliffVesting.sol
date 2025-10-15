// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract CliffVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable cliff;
    uint256 public immutable vestingEnd;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _cliffMonths,      // 6 for team
        uint256 _vestingMonths     // 18 for team (after cliff)
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        require(_cliffMonths > 0, "Invalid cliff");
        require(_vestingMonths > 0, "Invalid vesting period");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        cliff = _cliffMonths * 30 days;
        vestingEnd = startTime + (_cliffMonths + _vestingMonths) * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        if (block.timestamp < startTime + cliff) {
            return 0; // Nothing unlocked before cliff
        }
        
        if (block.timestamp >= vestingEnd) {
            return totalAllocation; // 100% unlocked after full vesting
        }
        
        uint256 vestingDuration = vestingEnd - (startTime + cliff);
        uint256 elapsedSinceCliff = block.timestamp - (startTime + cliff);
        
        return (totalAllocation * elapsedSinceCliff) / vestingDuration;
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
