// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./AirdropVesting.sol";
import "./LinearVesting.sol";
import "./CliffVesting.sol";

/**
 * @title VestingDeployer
 * @notice Helper contract to deploy vesting contracts
 * @dev Used by TokenFactory to avoid contract size limits
 *      Deploying vesting inline would embed bytecode in factory (exceeds 24KB)
 *      This pattern keeps TokenFactory small while maintaining atomic deployment
 */
contract VestingDeployer {
    address public immutable factory;
    
    event VestingContractsDeployed(
        address indexed pool,
        address airdropVesting,
        address marketingVesting,
        address teamVesting
    );
    
    constructor(address _factory) {
        require(_factory != address(0), "Invalid factory");
        factory = _factory;
    }
    
    /**
     * @notice Deploy all three vesting contracts
     * @dev Only callable by TokenFactory during token creation
     */
    function deployVestingContracts(
        address pool,
        address airdropBeneficiary,
        address marketingBeneficiary,
        address teamBeneficiary,
        uint256 airdropTokens,
        uint256 marketingTokens,
        uint256 teamTokens,
        uint256 /* deploymentTimestamp - unused, contracts use block.timestamp */
    ) external returns (
        address airdropVesting,
        address marketingVesting,
        address teamVesting
    ) {
        require(msg.sender == factory, "Only factory");
        require(pool != address(0), "Invalid pool");
        
        // Deploy AirdropVesting (5% daily unlock)
        if (airdropTokens > 0) {
            AirdropVesting av = new AirdropVesting(
                pool,
                airdropBeneficiary,
                airdropTokens
            );
            airdropVesting = address(av);
        }
        
        // Deploy LinearVesting for marketing (12-month linear)
        if (marketingTokens > 0) {
            LinearVesting mv = new LinearVesting(
                pool,
                marketingBeneficiary,
                marketingTokens,
                12  // 12 months
            );
            marketingVesting = address(mv);
        }
        
        // Deploy CliffVesting for team (6mo cliff + 18mo vest)
        if (teamTokens > 0) {
            CliffVesting tv = new CliffVesting(
                pool,
                teamBeneficiary,
                teamTokens,
                6,   // 6 month cliff
                18   // 18 month vesting (after cliff)
            );
            teamVesting = address(tv);
        }
        
        emit VestingContractsDeployed(pool, airdropVesting, marketingVesting, teamVesting);
        
        return (airdropVesting, marketingVesting, teamVesting);
    }
}
