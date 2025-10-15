// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./AirdropVesting.sol";
import "./LinearVesting.sol";
import "./CliffVesting.sol";

contract VestingManager {
    address public immutable factory;
    
    struct VestingContracts {
        address airdropVesting;
        uint256 airdropTokens;
        address marketingVesting;
        uint256 marketingTokens;
        address teamVesting;
        uint256 teamTokens;
    }
    
    constructor(address _factory) {
        require(_factory != address(0), "Invalid factory address");
        factory = _factory;
    }
    
    function deployVestingContracts(
        address poolAddress,
        uint256 totalSupply,
        uint8 reservedPercentage,
        uint8 airdropsAllocation,
        uint8 marketingAllocation,
        uint8 teamAllocation,
        address airdropTreasuryAddress,
        address creatorAddress
    ) external returns (VestingContracts memory result) {
        require(msg.sender == factory, "Only factory can deploy vesting contracts");
        require(poolAddress != address(0), "Invalid pool");
        require(totalSupply > 0, "Invalid supply");
        require(reservedPercentage > 0 && reservedPercentage <= 25, "Invalid reserve %");
        require(airdropTreasuryAddress != address(0), "Invalid airdrop treasury");
        require(creatorAddress != address(0), "Invalid creator");
        
        uint256 totalAllocations = airdropsAllocation + marketingAllocation + teamAllocation;
        require(totalAllocations == 100, "Allocations must sum to 100%");
        
        uint256 totalVesting = totalSupply * reservedPercentage / 100;
        
        result.airdropTokens = totalVesting * airdropsAllocation / 100;
        result.marketingTokens = totalVesting * marketingAllocation / 100;
        result.teamTokens = totalVesting * teamAllocation / 100;
        
        if (result.airdropTokens > 0) {
            require(result.airdropTokens >= 100 * 10**18, "Airdrop allocation too small");
            
            AirdropVesting av = new AirdropVesting(
                poolAddress,
                airdropTreasuryAddress,
                result.airdropTokens
            );
            result.airdropVesting = address(av);
        }
        
        if (result.marketingTokens > 0) {
            require(result.marketingTokens >= 100 * 10**18, "Marketing allocation too small");
            
            LinearVesting mv = new LinearVesting(
                poolAddress,
                creatorAddress,
                result.marketingTokens,
                12
            );
            result.marketingVesting = address(mv);
        }
        
        if (result.teamTokens > 0) {
            require(result.teamTokens >= 100 * 10**18, "Team allocation too small");
            
            CliffVesting tv = new CliffVesting(
                poolAddress,
                creatorAddress,
                result.teamTokens,
                6,
                18
            );
            result.teamVesting = address(tv);
        }
        
        return result;
    }
}
