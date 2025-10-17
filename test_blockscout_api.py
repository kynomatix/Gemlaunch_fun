#!/usr/bin/env python3
"""
Blockscout API Discovery - Testing REST API instead of GraphQL
The GraphQL endpoints don't work - trying REST API approach
"""
import requests
import json

base_url = "https://explorer.testnet.kasplextest.xyz"

# Test REST API endpoints
rest_endpoints = [
    f"{base_url}/api?module=account&action=tokentx&address=0x123",  # Token transfers
    f"{base_url}/api/v2/addresses",  # V2 API
    f"{base_url}/api/v2/transactions",  # V2 transactions
]

print("🔍 Testing Blockscout REST API...")
print("=" * 60)

# Try to get a real deployed token address from database
try:
    import sys
    sys.path.insert(0, '.')
    from app import app
    from models import Token
    
    with app.app_context():
        token = Token.query.filter_by(deployment_status='deployed').first()
        if token and token.contract_address:
            test_address = token.contract_address
            print(f"Using real token address: {test_address}\n")
        else:
            test_address = "0x0000000000000000000000000000000000000000"
            print("No deployed tokens found, using dummy address\n")
except Exception as e:
    test_address = "0x0000000000000000000000000000000000000000"
    print(f"Could not load token from database: {e}\n")

# Test different API approaches
tests = [
    {
        "name": "Token Transactions (REST API)",
        "url": f"{base_url}/api",
        "params": {
            "module": "account",
            "action": "tokentx",
            "address": test_address
        }
    },
    {
        "name": "Address Transactions (REST API)",
        "url": f"{base_url}/api",
        "params": {
            "module": "account",
            "action": "txlist",
            "address": test_address
        }
    },
    {
        "name": "Token Info (REST API)",
        "url": f"{base_url}/api",
        "params": {
            "module": "token",
            "action": "getToken",
            "contractaddress": test_address
        }
    },
    {
        "name": "V2 Addresses API",
        "url": f"{base_url}/api/v2/addresses/{test_address}",
        "params": {}
    },
    {
        "name": "V2 Transactions API",
        "url": f"{base_url}/api/v2/addresses/{test_address}/transactions",
        "params": {}
    },
]

working_apis = []

for test in tests:
    try:
        print(f"\nTesting: {test['name']}")
        print(f"  URL: {test['url']}")
        
        response = requests.get(
            test['url'],
            params=test['params'],
            headers={"Accept": "application/json"},
            timeout=10
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.ok:
            try:
                data = response.json()
                print(f"  ✅ SUCCESS - Response type: {type(data)}")
                print(f"  Preview: {str(data)[:200]}...")
                working_apis.append(test['name'])
            except json.JSONDecodeError:
                print(f"  ❌ Not JSON: {response.text[:100]}")
        else:
            print(f"  ❌ Failed: {response.text[:150]}")
    except Exception as e:
        print(f"  ❌ Error: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 60)
print(f"\nWorking APIs: {len(working_apis)}")
for api in working_apis:
    print(f"  ✅ {api}")

if working_apis:
    print("\n🎯 We can use the REST API instead of GraphQL!")
else:
    print("\n⚠️  No working APIs found - need to investigate further")
