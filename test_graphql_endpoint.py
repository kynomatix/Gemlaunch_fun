#!/usr/bin/env python3
"""
GraphQL Endpoint Discovery - Phase 0
Tests multiple possible Blockscout GraphQL endpoints to find the working one
"""
import requests
import json

# Test different possible endpoints
endpoints = [
    "https://explorer.testnet.kasplextest.xyz/graphiql",
    "https://explorer.testnet.kasplextest.xyz/api/v2/graphql",
    "https://explorer.testnet.kasplextest.xyz/graphql",
    "https://explorer.testnet.kasplextest.xyz/api/graphql",
]

# Simple test query to check if endpoint is working
test_query = {
    "query": "{ __schema { types { name } } }"
}

print("🔍 Testing Blockscout GraphQL Endpoints...")
print("=" * 60)

working_endpoints = []

for endpoint in endpoints:
    try:
        print(f"\nTesting: {endpoint}")
        response = requests.post(
            endpoint, 
            json=test_query,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.ok:
            data = response.json()
            if 'data' in data or 'errors' not in data:
                print(f"✅ SUCCESS: {endpoint}")
                print(f"   Status: {response.status_code}")
                print(f"   Response preview: {str(data)[:150]}...")
                working_endpoints.append(endpoint)
            else:
                print(f"❌ GraphQL Error: {data.get('errors', 'Unknown error')}")
        else:
            print(f"❌ HTTP Error: Status {response.status_code}")
            print(f"   Response: {response.text[:150]}")
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout: {endpoint}")
    except Exception as e:
        print(f"❌ Error: {endpoint} - {type(e).__name__}: {str(e)[:100]}")

print("\n" + "=" * 60)
print(f"Found {len(working_endpoints)} working endpoint(s):")
for ep in working_endpoints:
    print(f"  ✅ {ep}")

if working_endpoints:
    print(f"\n🎯 Use this endpoint: {working_endpoints[0]}")
else:
    print("\n⚠️  No working endpoints found!")
    print("Next steps:")
    print("1. Open https://explorer.testnet.kasplextest.xyz/graphiql in browser")
    print("2. Open DevTools → Network tab")
    print("3. Run a test query")
    print("4. Look for the POST request to find actual endpoint")
