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
 * 
 * SPEC ALIGNMENT:
 * - Implements PRO_TOKEN_VESTING_SPECIFICATION_V2.md lines 347-396 logic
 * - Returns address(0) for zero allocations (e.g., 100/0/0 or 0/100/0)
 * - Only deploys contracts when allocation > 0 (spec behavior)
 * - Functionally identical to direct deployment, just delegated for size
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
     *      AUDIT FIX H-2: Added validation for beneficiaries, minimum amounts, and pool contract
     *      AUDIT FIX M-2: Removed unused deploymentTimestamp parameter
     */
    function deployVestingContracts(
        address pool,
        address airdropBeneficiary,
        address marketingBeneficiary,
        address teamBeneficiary,
        uint256 airdropTokens,
        uint256 marketingTokens,
        uint256 teamTokens
    ) external returns (
        address airdropVesting,
        address marketingVesting,
        address teamVesting
    ) {
        require(msg.sender == factory, "Only factory");
        require(pool != address(0), "Invalid pool");
        
        // AUDIT FIX H-2: Validate pool is a contract
        uint256 poolSize;
        assembly {
            poolSize := extcodesize(pool)
        }
        require(poolSize > 0, "Pool must be contract");
        
        // Deploy AirdropVesting (5% daily unlock) with validation
        if (airdropTokens > 0) {
            require(airdropBeneficiary != address(0), "Invalid airdrop beneficiary");
            require(airdropTokens >= 100 * 10**18, "Airdrop allocation too small");
            
            AirdropVesting av = new AirdropVesting(
                pool,
                airdropBeneficiary,
                airdropTokens
            );
            airdropVesting = address(av);
        }
        
        // Deploy LinearVesting for marketing (12-month linear) with validation
        if (marketingTokens > 0) {
            require(marketingBeneficiary != address(0), "Invalid marketing beneficiary");
            require(marketingTokens >= 100 * 10**18, "Marketing allocation too small");
            
            LinearVesting mv = new LinearVesting(
                pool,
                marketingBeneficiary,
                marketingTokens,
                12  // 12 months
            );
            marketingVesting = address(mv);
        }
        
        // Deploy CliffVesting for team (6mo cliff + 18mo vest) with validation
        if (teamTokens > 0) {
            require(teamBeneficiary != address(0), "Invalid team beneficiary");
            require(teamTokens >= 100 * 10**18, "Team allocation too small");
            
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
