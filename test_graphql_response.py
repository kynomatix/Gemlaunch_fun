#!/usr/bin/env python3
"""
Check what /graphiql actually returns when POSTed to
"""
import requests

GRAPHQL_ENDPOINT = "https://explorer.testnet.kasplextest.xyz/graphiql"

query = {
    "query": "{ __schema { types { name } } }"
}

print("Testing POST to /graphiql...")
response = requests.post(
    GRAPHQL_ENDPOINT,
    json=query,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print(f"\nFirst 500 chars of response:")
print(response.text[:500])
print("\n" + "="*60)

# Also try with the query as a string in the body
print("\nTrying alternative format (query as string)...")
response2 = requests.post(
    GRAPHQL_ENDPOINT,
    data=query['query'],
    headers={
        "Content-Type": "application/graphql",
    }
)

print(f"Status: {response2.status_code}")
print(f"Content-Type: {response2.headers.get('content-type')}")
print(f"\nFirst 500 chars:")
print(response2.text[:500])
