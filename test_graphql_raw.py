#!/usr/bin/env python3
"""
Test GraphQL with RAW query body (not JSON) as architect instructed
Blockscout expects: POST with raw GraphQL and Content-Type: application/graphql
"""
import requests
import json

GRAPHQL_ENDPOINT = "https://explorer.testnet.kasplextest.xyz/graphiql"

# Raw GraphQL query (not wrapped in JSON)
raw_query = """
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

print("🧪 Testing GraphQL with RAW body (architect's solution)...")
print(f"Endpoint: {GRAPHQL_ENDPOINT}")
print("=" * 60)

try:
    # POST with raw GraphQL body and application/graphql content type
    response = requests.post(
        GRAPHQL_ENDPOINT,
        data=raw_query.strip(),
        headers={
            "Content-Type": "application/graphql",
            "Accept": "application/json"
        },
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    
    if response.ok:
        # Check if response is JSON
        if 'application/json' in response.headers.get('Content-Type', ''):
            data = response.json()
            print("\n✅ SUCCESS! GraphQL API is working!")
            print(f"\nResponse structure: {list(data.keys())}")
            
            if 'data' in data:
                print(f"Query type: {data['data']['__schema']['queryType']['name']}")
                print(f"Total types: {len(data['data']['__schema']['types'])}")
                print(f"First 5 types: {[t['name'] for t in data['data']['__schema']['types'][:5]]}")
            
            print(f"\n🎯 CORRECT ENDPOINT: {GRAPHQL_ENDPOINT}")
            print("🎯 CORRECT METHOD: POST with raw GraphQL body")
            print("🎯 CORRECT HEADER: Content-Type: application/graphql")
        else:
            print(f"❌ Not JSON response")
            print(f"Response preview: {response.text[:200]}")
    else:
        print(f"❌ Failed with status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")

print("\n" + "=" * 60)
