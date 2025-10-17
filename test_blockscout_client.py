#!/usr/bin/env python3
"""
Test BlockscoutClient with correct GraphQL endpoint
"""
import sys
import logging
from services.blockscout_client import get_blockscout_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("🧪 Testing BlockscoutClient")
    print("=" * 60)
    
    # Get client
    client = get_blockscout_client()
    
    # Test 1: Health check
    print("\n1️⃣ Health Check...")
    is_healthy = client.health_check()
    print(f"Result: {'✅ PASS' if is_healthy else '❌ FAIL'}")
    
    if not is_healthy:
        print("❌ GraphQL API not accessible")
        return 1
    
    # Test 2: Get token transfers for a known token
    # Using real token from database
    print("\n2️⃣ Token Transfers Query...")
    test_token = "0x82a7290b0ead0f6626a3ee00ad8c09be9f7bfd3c"  # Kaspataur (KTAR)
    transfers = client.get_token_transfers(test_token, first=5)
    print(f"Result: Fetched {len(transfers)} transfers")
    if transfers:
        print(f"Sample transfer: {transfers[0]}")
    
    # Test 3: Get transaction
    print("\n3️⃣ Transaction Query...")
    # Test with any transaction hash
    if transfers and len(transfers) > 0:
        tx_hash = transfers[0]["tx_hash"]
        tx = client.get_transaction(tx_hash)
        if tx:
            print(f"✅ Transaction found: block {tx.get('blockNumber')}")
        else:
            print("❌ Transaction not found")
    else:
        print("⏭️  Skipped (no transfers to test)")
    
    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
