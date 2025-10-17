#!/usr/bin/env python3
"""
Test /api/v2/graphql endpoint (suggested by user's helper)
Also test with CORS headers to simulate browser request
"""
import requests
import json

# Try the V2 endpoint specifically
endpoints_to_test = [
    "https://explorer.testnet.kasplextest.xyz/api/v2/graphql",
    "https://explorer.testnet.kasplextest.xyz/graphiql",
]

# Simple introspection query
query_payload = {
    "query": "{ __schema { queryType { name } } }"
}

print("🔍 Testing GraphQL with V2 endpoint and CORS headers...")
print("=" * 60)

for endpoint in endpoints_to_test:
    print(f"\n📍 Testing: {endpoint}")
    print("-" * 60)
    
    # Test 1: Standard JSON GraphQL request
    print("Test 1: Standard GraphQL JSON request")
    try:
        response = requests.post(
            endpoint,
            json=query_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=10
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type')}")
        
        if 'application/json' in response.headers.get('Content-Type', ''):
            data = response.json()
            print(f"  ✅ Got JSON response!")
            print(f"  Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"  ✅✅ SUCCESS! GraphQL is working!")
                print(f"  Query type: {data['data']['__schema']['queryType']}")
                break
        else:
            print(f"  ❌ Not JSON (got: {response.headers.get('content-type')})")
            print(f"  Preview: {response.text[:100]}")
    except Exception as e:
        print(f"  ❌ Error: {type(e).__name__}: {str(e)[:100]}")
    
    # Test 2: With CORS headers (simulate browser)
    print("\nTest 2: With CORS headers (simulating browser)")
    try:
        response = requests.post(
            endpoint,
            json=query_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://explorer.testnet.kasplextest.xyz",
                "Referer": "https://explorer.testnet.kasplextest.xyz/graphiql",
                "User-Agent": "Mozilla/5.0 (compatible)"
            },
            timeout=10
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('content-type')}")
        
        if 'application/json' in response.headers.get('Content-Type', ''):
            data = response.json()
            print(f"  ✅ Got JSON with CORS headers!")
            print(f"  Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"  ✅✅ SUCCESS! GraphQL works with CORS headers!")
                print(f"  Query type: {data['data']['__schema']['queryType']}")
                break
        else:
            print(f"  ❌ Still not JSON")
    except Exception as e:
        print(f"  ❌ Error: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 60)
