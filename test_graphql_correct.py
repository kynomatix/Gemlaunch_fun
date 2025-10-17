#!/usr/bin/env python3
"""
Test GraphQL endpoint correctly - /graphiql accepts POST requests for API
"""
import requests
import json

# The CORRECT endpoint - same URL for UI and API
GRAPHQL_ENDPOINT = "https://explorer.testnet.kasplextest.xyz/graphiql"

# Test query
query = {
    "query": """
        {
            __schema {
                types {
                    name
                }
            }
        }
    """
}

print("🧪 Testing GraphQL API at /graphiql endpoint...")
print(f"Endpoint: {GRAPHQL_ENDPOINT}")
print("=" * 60)

try:
    # POST request with JSON (this is the API call)
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
    
    if response.ok:
        data = response.json()
        print("✅ SUCCESS! GraphQL API is working!")
        print(f"\nResponse type: {type(data)}")
        
        if 'data' in data:
            print(f"Schema types found: {len(data['data']['__schema']['types'])}")
            print(f"First 5 types: {[t['name'] for t in data['data']['__schema']['types'][:5]]}")
        else:
            print(f"Response: {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")

print("\n" + "=" * 60)
print("If this shows SUCCESS, /graphiql IS the correct GraphQL endpoint!")
