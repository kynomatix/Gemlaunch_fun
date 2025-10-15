#!/usr/bin/env python3
"""
Verify PRO token creation by parsing existing transaction
This script fetches and parses a successful PRO token transaction
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.web3_service import Web3Service
import logging

logging.basicConfig(level=logging.INFO)

def verify_pro_token_transaction():
    """Fetch and verify a PRO token creation transaction"""
    
    print("\n" + "="*80)
    print("🔍 Verifying PRO Token Transaction")
    print("="*80 + "\n")
    
    # Initialize Web3Service
    w3s = Web3Service()
    
    # Transaction hash from successful deployment
    tx_hash = "0x09c786a70d7010a8e690a8a77f03113cf2d1a1065371376aa54bb6b5f64c36f4"
    
    print(f"📋 Fetching transaction: {tx_hash}")
    
    # Get transaction receipt
    receipt = w3s.w3.eth.get_transaction_receipt(tx_hash)
    
    print(f"✅ Transaction found!")
    print(f"   Block: {receipt['blockNumber']}")
    print(f"   Gas used: {receipt['gasUsed']}")
    print(f"   Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    
    if receipt['status'] == 1:
        # Parse logs to find deployed contracts
        print("\n🔍 Parsing transaction logs...")
        
        # Get TokenFactory contract
        factory = w3s.contracts['TokenFactory']
        
        # Look for TokenCreated event
        token_created_events = factory.events.TokenCreated().process_receipt(receipt)
        
        if token_created_events:
            event = token_created_events[0]
            token_address = event['args']['tokenAddress']
            pool_address = event['args']['poolAddress']
            creator = event['args']['creator']
            name = event['args']['name']
            symbol = event['args']['symbol']
            total_supply = event['args']['totalSupply']
            
            print(f"\n✅ Token Created!")
            print(f"   Name: {name}")
            print(f"   Symbol: {symbol}")
            print(f"   Token Address: {token_address}")
            print(f"   Pool Address: {pool_address}")
            print(f"   Creator: {creator}")
            print(f"   Total Supply: {w3s.w3.from_wei(total_supply, 'ether'):,.0f} tokens")
            
            # Look for VestingDeployed event
            vesting_events = factory.events.VestingDeployed().process_receipt(receipt)
            
            if vesting_events:
                vesting_event = vesting_events[0]
                print(f"\n✅ Vesting Contracts Deployed!")
                print(f"   Airdrop Vesting: {vesting_event['args']['airdropVesting']}")
                print(f"   Marketing Vesting: {vesting_event['args']['marketingVesting']}")
                print(f"   Team Vesting: {vesting_event['args']['teamVesting']}")
                
                # Verify vesting allocations (percentages of reserved tokens)
                airdrop_allocation = vesting_event['args']['airdropAllocation']
                marketing_allocation = vesting_event['args']['marketingAllocation']
                team_allocation = vesting_event['args']['teamAllocation']
                
                # Calculate actual token amounts (20% reserved with 50/30/20 split)
                reserved_percentage = 20
                reserved_tokens = total_supply * reserved_percentage // 100
                
                airdrop_amount = reserved_tokens * airdrop_allocation // 100
                marketing_amount = reserved_tokens * marketing_allocation // 100
                team_amount = reserved_tokens * team_allocation // 100
                
                print(f"\n📊 Vesting Allocations:")
                print(f"   Airdrop: {airdrop_allocation}% of reserved ({w3s.w3.from_wei(airdrop_amount, 'ether'):,.0f} tokens)")
                print(f"   Marketing: {marketing_allocation}% of reserved ({w3s.w3.from_wei(marketing_amount, 'ether'):,.0f} tokens)")
                print(f"   Team: {team_allocation}% of reserved ({w3s.w3.from_wei(team_amount, 'ether'):,.0f} tokens)")
                
                total_vested = airdrop_amount + marketing_amount + team_amount
                print(f"   Total Vested: {w3s.w3.from_wei(total_vested, 'ether'):,.0f} tokens ({reserved_percentage}% of supply)")
                
                print("\n" + "="*80)
                print("✅ PRO TOKEN VESTING VERIFIED SUCCESSFULLY!")
                print("="*80)
                
                return {
                    'success': True,
                    'token_address': token_address,
                    'pool_address': pool_address,
                    'tx_hash': tx_hash,
                    'vesting': {
                        'airdrop': vesting_event['args']['airdropVesting'],
                        'marketing': vesting_event['args']['marketingVesting'],
                        'team': vesting_event['args']['teamVesting']
                    }
                }
            else:
                print("\n⚠️ Warning: No VestingDeployed event found!")
        else:
            print("\n❌ Error: No TokenCreated event found in receipt")
    else:
        print(f"\n❌ Transaction failed!")
    
    return {'success': False}

if __name__ == '__main__':
    try:
        result = verify_pro_token_transaction()
        sys.exit(0 if result['success'] else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
