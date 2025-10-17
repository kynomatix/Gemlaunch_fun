#!/usr/bin/env python3
"""
Test the ACTUAL GraphQL endpoint found from DevTools:
POST https://explorer.testnet.kasplextest.xyz/api/v1/graphql
"""
import requests
import json

# THE CORRECT ENDPOINT (from DevTools)
GRAPHQL_ENDPOINT = "https://explorer.testnet.kasplextest.xyz/api/v1/graphql"

# Test introspection query
query = {
    "query": """
        {
            __schema {
                queryType {
                    name
                }
                types {
                    name
                }
            }
        }
    """
}

print("🎯 Testing ACTUAL GraphQL endpoint from DevTools...")
print(f"Endpoint: {GRAPHQL_ENDPOINT}")
print("=" * 60)

try:
    response = requests.post(
        GRAPHQL_ENDPOINT,
        json=query,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    
    if response.ok:
        if 'application/json' in response.headers.get('Content-Type', ''):
            data = response.json()
            print("\n✅✅✅ SUCCESS! GraphQL IS WORKING!")
            print(f"\nResponse keys: {list(data.keys())}")
            
            if 'data' in data:
                print(f"\nQuery type: {data['data']['__schema']['queryType']['name']}")
                print(f"Total types: {len(data['data']['__schema']['types'])}")
                print(f"\nFirst 10 types:")
                for t in data['data']['__schema']['types'][:10]:
                    print(f"  - {t['name']}")
                    
                print(f"\n🎉 CORRECT ENDPOINT: {GRAPHQL_ENDPOINT}")
            else:
                print(f"\nFull response: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"❌ Not JSON")
            print(f"Response: {response.text[:200]}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")

print("\n" + "=" * 60)
