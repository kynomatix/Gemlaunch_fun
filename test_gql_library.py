#!/usr/bin/env python3
"""
Test GraphQL using gql library (as instructed)
"""
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

# Use /graphiql endpoint as instructed
BLOCKSCOUT_GRAPHQL = "https://explorer.testnet.kasplextest.xyz/graphiql"

print("🧪 Testing GraphQL with gql library...")
print(f"Endpoint: {BLOCKSCOUT_GRAPHQL}")
print("=" * 60)

try:
    # Configure transport
    transport = RequestsHTTPTransport(
        url=BLOCKSCOUT_GRAPHQL,
        use_json=True,
        headers={
            "Content-Type": "application/json",
        },
    )
    
    # Create client
    client = Client(transport=transport, fetch_schema_from_transport=False)
    
    # Test query
    query = gql("""
        {
            __schema {
                types {
                    name
                }
            }
        }
    """)
    
    print("Executing GraphQL query...")
    result = client.execute(query)
    
    print("✅ SUCCESS! GraphQL is working!")
    print(f"Schema types: {len(result['__schema']['types'])}")
    print(f"First 5 types: {[t['name'] for t in result['__schema']['types'][:5]]}")
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}")
    print(f"Details: {str(e)[:500]}")
    
    # Try to get more details
    if hasattr(e, 'response'):
        print(f"\nResponse status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
        if hasattr(e.response, 'text'):
            print(f"Response preview: {e.response.text[:200]}")

print("\n" + "=" * 60)
