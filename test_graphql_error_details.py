#!/usr/bin/env python3
"""
Check what error /api/v2/graphql returns
"""
import requests
import json

endpoint = "https://explorer.testnet.kasplextest.xyz/api/v2/graphql"

query_payload = {
    "query": "{ __schema { queryType { name } } }"
}

response = requests.post(
    endpoint,
    json=query_payload,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print(f"\nFull Response:")
print(json.dumps(response.json(), indent=2))
