#!/usr/bin/env python3
"""
PRO Token Vesting Integration Test
===================================

This script tests the PRO token vesting functionality by:
1. Creating a test PRO token in the database with vesting addresses
2. Querying database to verify vesting addresses are persisted
3. Testing vesting status API endpoint
4. Testing withdrawal endpoint builders
5. Capturing all evidence for documentation

Uses deployed PRO token data from TEST_PRO_TOKEN_RESULTS.md (Test #2)
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Token

# Test data from TEST_PRO_TOKEN_RESULTS.md (Test #2)
TEST_TOKEN_DATA = {
    'contract_address': '0x9b675BEf3e602d5F921405502aEB53dEfbe6d185',
    'name': 'Test PRO Token',
    'symbol': 'TPRO',
    'description': 'Integration test PRO token with vesting',
    'total_supply': 1_000_000_000 * 10**18,  # 1 billion tokens
    'reserved_percentage': 20.0,  # 20% reserved
    'marketing_vesting_address': '0x1CBBC988AfF56c0a7Cb7955662f2689444E83E4D',
    'team_vesting_address': '0x82D55a12c103492Fe0a7015712c89016d20de086',
    'airdrop_vesting_address': '0x52ff8F85ED69fa618ac97C28A2B6fc46A7e3111d',
    'deployment_status': 'deployed',
    'deployment_tx': '0xc23fdcb95659c7574af37f07bb284a8f521d95e76ca8cf53385835ebafe257ce',
    'deployment_block_number': 8130541,
}

# Test user wallet address
TEST_WALLET = '0x1234567890abcdef1234567890abcdef12345678'

# Base URL for API requests
BASE_URL = 'http://localhost:5000'

def print_header(title):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80 + "\n")

def print_subheader(title):
    """Print a formatted subsection header"""
    print(f"\n--- {title} ---\n")

def create_test_data():
    """Create test user and PRO token in database"""
    print_header("STEP 1: DATABASE SETUP")
    
    with app.app_context():
        # Create or get test user
        user = User.query.filter_by(wallet_address=TEST_WALLET.lower()).first()
        if not user:
            user = User(
                wallet_address=TEST_WALLET.lower(),
                display_name='Test User',
                wallet_type='test'
            )
            db.session.add(user)
            db.session.commit()
            print(f"✅ Created test user (ID: {user.id}, Wallet: {user.wallet_address})")
        else:
            print(f"✅ Test user already exists (ID: {user.id}, Wallet: {user.wallet_address})")
        
        # Create or get test PRO token
        token = Token.query.filter_by(
            contract_address=TEST_TOKEN_DATA['contract_address'].lower()
        ).first()
        
        if not token:
            token = Token(
                creator_id=user.id,
                name=TEST_TOKEN_DATA['name'],
                symbol=TEST_TOKEN_DATA['symbol'],
                description=TEST_TOKEN_DATA['description'],
                contract_address=TEST_TOKEN_DATA['contract_address'].lower(),
                total_supply=TEST_TOKEN_DATA['total_supply'],
                reserved_percentage=TEST_TOKEN_DATA['reserved_percentage'],
                marketing_vesting_address=TEST_TOKEN_DATA['marketing_vesting_address'].lower(),
                team_vesting_address=TEST_TOKEN_DATA['team_vesting_address'].lower(),
                airdrop_vesting_address=TEST_TOKEN_DATA['airdrop_vesting_address'].lower(),
                deployment_status=TEST_TOKEN_DATA['deployment_status'],
                deployment_tx=TEST_TOKEN_DATA['deployment_tx'],
                deployment_block_number=TEST_TOKEN_DATA['deployment_block_number'],
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(token)
            db.session.commit()
            print(f"✅ Created test PRO token (ID: {token.id}, Symbol: {token.symbol})")
        else:
            # Update vesting addresses if missing
            if not token.marketing_vesting_address:
                token.marketing_vesting_address = TEST_TOKEN_DATA['marketing_vesting_address'].lower()
                token.team_vesting_address = TEST_TOKEN_DATA['team_vesting_address'].lower()
                token.airdrop_vesting_address = TEST_TOKEN_DATA['airdrop_vesting_address'].lower()
                db.session.commit()
                print(f"✅ Updated vesting addresses for existing token (ID: {token.id})")
            else:
                print(f"✅ Test PRO token already exists (ID: {token.id}, Symbol: {token.symbol})")
        
        return user.id, token.id

def verify_database():
    """Query database to verify vesting addresses are persisted"""
    print_header("STEP 2: DATABASE VERIFICATION")
    
    with app.app_context():
        token = Token.query.filter_by(
            contract_address=TEST_TOKEN_DATA['contract_address'].lower()
        ).first()
        
        if not token:
            print("❌ ERROR: Token not found in database")
            return None
        
        print(f"Token ID: {token.id}")
        print(f"Name: {token.name}")
        print(f"Symbol: {token.symbol}")
        print(f"Contract Address: {token.contract_address}")
        print(f"Reserved Percentage: {token.reserved_percentage}%")
        print(f"Deployment Status: {token.deployment_status}")
        print(f"Deployment Tx: {token.deployment_tx}")
        
        print_subheader("Vesting Addresses")
        print(f"Marketing Vesting: {token.marketing_vesting_address}")
        print(f"Team Vesting:      {token.team_vesting_address}")
        print(f"Airdrop Vesting:   {token.airdrop_vesting_address}")
        
        if token.marketing_vesting_address and token.team_vesting_address and token.airdrop_vesting_address:
            print("\n✅ All vesting addresses are populated in database")
        else:
            print("\n❌ ERROR: Some vesting addresses are missing")
            
        return token.id

def test_vesting_status_endpoint(token_id):
    """Test the vesting status API endpoint"""
    print_header("STEP 3: VESTING STATUS API TEST")
    
    url = f"{BASE_URL}/api/token/{token_id}/vesting/status"
    print(f"Testing endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"\nHTTP Status: {response.status_code}")
        
        # Pretty print response JSON
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
            print("\nResponse JSON:")
            print(json.dumps(response_data, indent=2))
            
            # Verify response structure
            if response.status_code == 200 and response_data.get('success'):
                print("\n✅ Vesting status endpoint returned success")
                
                vesting = response_data.get('vesting', {})
                if vesting.get('marketing') and vesting.get('team') and vesting.get('airdrop'):
                    print("✅ All vesting contracts (marketing, team, airdrop) present in response")
                else:
                    print("⚠️  Some vesting contracts missing in response")
            else:
                print(f"\n⚠️  API returned non-success response")
        else:
            print(f"\nResponse body:\n{response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to server. Is the app running on port 5000?")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_withdrawal_endpoints(token_id):
    """Test the withdrawal endpoint builders"""
    print_header("STEP 4: WITHDRAWAL ENDPOINT TESTS")
    
    endpoints = [
        ('marketing', f"{BASE_URL}/api/token/{token_id}/vesting/withdraw-marketing"),
        ('team', f"{BASE_URL}/api/token/{token_id}/vesting/withdraw-team")
    ]
    
    results = []
    
    for vesting_type, url in endpoints:
        print_subheader(f"Testing {vesting_type.upper()} withdrawal endpoint")
        print(f"URL: {url}")
        
        try:
            payload = {'creator_address': TEST_WALLET}
            print(f"Request payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, timeout=10)
            print(f"\nHTTP Status: {response.status_code}")
            
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data = response.json()
                print("\nResponse JSON:")
                print(json.dumps(response_data, indent=2))
                
                if response.status_code == 200 and response_data.get('success'):
                    print(f"\n✅ {vesting_type.capitalize()} withdrawal endpoint returned success")
                    results.append(True)
                else:
                    print(f"\n⚠️  {vesting_type.capitalize()} withdrawal endpoint returned non-success")
                    results.append(False)
            else:
                print(f"\nResponse body:\n{response.text}")
                results.append(False)
                
        except requests.exceptions.ConnectionError:
            print("❌ ERROR: Could not connect to server")
            results.append(False)
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            results.append(False)
    
    return all(results)

def run_integration_test():
    """Run the complete integration test suite"""
    print_header("PRO TOKEN VESTING INTEGRATION TEST")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        # Step 1: Create test data
        user_id, token_id = create_test_data()
        
        # Step 2: Verify database
        db_token_id = verify_database()
        if not db_token_id:
            print("\n❌ FAILED: Database verification failed")
            return False
        
        # Step 3: Test vesting status endpoint
        status_success = test_vesting_status_endpoint(token_id)
        
        # Step 4: Test withdrawal endpoints
        withdrawal_success = test_withdrawal_endpoints(token_id)
        
        # Final results
        print_header("TEST RESULTS SUMMARY")
        print(f"✅ Database Setup:        {'PASSED' if token_id else 'FAILED'}")
        print(f"✅ Database Verification: {'PASSED' if db_token_id else 'FAILED'}")
        print(f"{'✅' if status_success else '❌'} Vesting Status API:   {'PASSED' if status_success else 'FAILED'}")
        print(f"{'✅' if withdrawal_success else '❌'} Withdrawal APIs:      {'PASSED' if withdrawal_success else 'FAILED'}")
        
        all_passed = token_id and db_token_id and status_success and withdrawal_success
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print("\n⚠️  SOME TESTS FAILED - Review output above")
        
        print(f"\nTest Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*80 + "\n")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = run_integration_test()
    sys.exit(0 if success else 1)
