#!/usr/bin/env python3
"""
Test PRO token creation with vesting on Kasplex testnet
This script creates a PRO token and verifies vesting contracts are deployed
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.web3_service import Web3Service
import logging

logging.basicConfig(level=logging.INFO)

def test_pro_token_creation():
    """Create a test PRO token with vesting and verify deployment"""
    
    print("\n" + "="*80)
    print("🧪 Testing PRO Token Creation with Vesting")
    print("="*80 + "\n")
    
    # Initialize Web3Service
    w3s = Web3Service()
    
    # Test PRO token parameters
    token_params = {
        'user_address': w3s.deployer_account.address,
        'name': 'Test Vesting Token',
        'symbol': 'TVEST',
        'total_supply': 1_000_000_000 * 10**18,  # 1 billion tokens
        'description': 'Testing PRO token vesting system',
        'image_url': 'https://ipfs.io/ipfs/QmTest123',
        'twitter_url': '',
        'telegram_url': '',
        'website_url': '',
        
        # PRO token settings
        'reserved_percentage': 20,  # 20% reserved for vesting
        'airdrops_allocation': 50,   # 50% of reserved = 10% total supply
        'marketing_allocation': 30,  # 30% of reserved = 6% total supply
        'team_allocation': 20,       # 20% of reserved = 4% total supply
        
        # Anti-bot settings
        'anti_bot_enabled': True
    }
    
    print("📋 Token Parameters:")
    print(f"   User Address: {token_params['user_address']}")
    print(f"   Name: {token_params['name']}")
    print(f"   Symbol: {token_params['symbol']}")
    print(f"   Total Supply: {token_params['total_supply'] // 10**18:,} tokens")
    print(f"   Reserved: {token_params['reserved_percentage']}%")
    print(f"   Allocations: Airdrop {token_params['airdrops_allocation']}%, Marketing {token_params['marketing_allocation']}%, Team {token_params['team_allocation']}%")
    print(f"   Anti-bot: {token_params['anti_bot_enabled']}")
    
    # Build transaction data
    print("\n🔨 Building transaction data...")
    tx_data = w3s.create_token_tx_data(
        user_address=token_params['user_address'],
        name=token_params['name'],
        symbol=token_params['symbol'],
        total_supply=token_params['total_supply'],
        description=token_params['description'],
        image_url=token_params['image_url'],
        twitter_url=token_params['twitter_url'],
        telegram_url=token_params['telegram_url'],
        website_url=token_params['website_url'],
        anti_bot_enabled=token_params['anti_bot_enabled'],
        reserved_percentage=token_params['reserved_percentage'],
        airdrops_allocation=token_params['airdrops_allocation'],
        marketing_allocation=token_params['marketing_allocation'],
        team_allocation=token_params['team_allocation']
    )
    
    print(f"   ✓ To: {tx_data['to']}")
    print(f"   ✓ Value: {tx_data['value']} wei")
    print(f"   ✓ Data length: {len(tx_data['data'])} bytes")
    
    # Sign and send transaction
    print("\n📤 Signing and sending transaction...")
    signed_txn = w3s.sign_transaction(tx_data, w3s.deployer_account.key)
    tx_hash = w3s.relay_transaction(signed_txn)
    
    print(f"\n✅ Transaction sent!")
    print(f"   Tx hash: {tx_hash}")
    print(f"   Explorer: http://explorer.testnet.kasplextest.xyz/tx/{tx_hash}")
    
    # Wait for confirmation
    print("\n⏳ Waiting for confirmation (this may take 30-60 seconds)...")
    receipt = w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print("\n🎉 Transaction confirmed!")
        print(f"   Block: {receipt['blockNumber']}")
        print(f"   Gas used: {receipt['gasUsed']}")
        
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
            
            print(f"\n✅ Token Created!")
            print(f"   Token Address: {token_address}")
            print(f"   Pool Address: {pool_address}")
            print(f"   Creator: {creator}")
            
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
                
                # Calculate actual token amounts
                total_supply = token_params['total_supply']
                reserved_percentage = token_params['reserved_percentage']
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
                print("✅ PRO TOKEN VESTING TEST SUCCESSFUL!")
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
                print("   This might be a BASIC token (reservedPercentage = 0)")
        else:
            print("\n❌ Error: No TokenCreated event found in receipt")
    else:
        print(f"\n❌ Transaction failed!")
        print(f"   Status: {receipt['status']}")
    
    return {'success': False}

if __name__ == '__main__':
    try:
        result = test_pro_token_creation()
        sys.exit(0 if result['success'] else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
