// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract LinearVesting is ReentrancyGuard {
    IERC20 public immutable token;
    address public immutable beneficiary;
    uint256 public immutable totalAllocation;
    uint256 public immutable startTime;
    uint256 public immutable duration;
    uint256 public withdrawn;
    
    event TokensWithdrawn(address indexed beneficiary, uint256 amount);
    
    constructor(
        address _token,
        address _beneficiary,
        uint256 _totalAllocation,
        uint256 _durationMonths  // 12 for marketing
    ) {
        require(_token != address(0), "Invalid token");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_totalAllocation > 0, "Invalid allocation");
        require(_durationMonths > 0, "Invalid duration");
        
        token = IERC20(_token);
        beneficiary = _beneficiary;
        totalAllocation = _totalAllocation;
        startTime = block.timestamp;
        duration = _durationMonths * 30 days;
    }
    
    function getUnlockedAmount() public view returns (uint256) {
        uint256 elapsed = block.timestamp - startTime;
        
        if (elapsed >= duration) {
            return totalAllocation; // 100% unlocked
        }
        
        return (totalAllocation * elapsed) / duration;
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
