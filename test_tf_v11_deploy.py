"""
Test script to create a token with TokenFactory V11 and test graduation
"""

import os
from services.web3_service import Web3Service
from web3 import Web3
import time

# Initialize Web3 Service
w3s = Web3Service()

print("\n" + "="*80)
print("🧪 TESTING TOKENFACTORY V11 - GRADUATION END-TO-END")
print("="*80 + "\n")

# Contract addresses
TF_V11 = "0x427B039bc381911a40AC25Fc50AB9e6f5633A5B1"
GC_V8 = "0x22F3cC689401462B6ceb85EF544E86FE27ad178f"

print(f"📋 Configuration:")
print(f"   TokenFactory V11: {TF_V11}")
print(f"   GraduationController V8: {GC_V8}")
print(f"   Oracle: {w3s.oracle_account.address}")
print()

# Token parameters
token_name = "V11 Test Token"
token_symbol = "V11T"
total_supply = 1_000_000_000  # 1B tokens

print(f"🪙 Token Parameters:")
print(f"   Name: {token_name}")
print(f"   Symbol: {token_symbol}")
print(f"   Total Supply: {total_supply:,}")
print()

# Build createToken transaction
print("🔨 Building createToken transaction...")
token_factory = w3s.contracts['TokenFactory']

tx = token_factory.functions.createToken(
    token_name,
    token_symbol,
    total_supply,
    "Test token for graduation with V11/V8 contracts",  # description
    "",  # imageUrl
    "",  # twitterUrl
    "",  # telegramUrl
    "",  # websiteUrl
    False,  # antiBotEnabled
    0,  # reservedPercentage (no vesting)
    0,  # airdropsAllocation
    0,  # marketingAllocation
    0   # teamAllocation
).build_transaction({
    'from': w3s.oracle_account.address,
    'gas': 15_000_000,
    'gasPrice': w3s.w3.eth.gas_price,
    'nonce': w3s.w3.eth.get_transaction_count(w3s.oracle_account.address),
})

print("✍️  Signing transaction...")
signed_tx = w3s.sign_transaction(tx)

print("📡 Sending transaction...")
tx_hash = w3s.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"   TX Hash: {tx_hash.hex()}")

print("\n⏳ Waiting for confirmation...")
receipt = w3s.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    print("✅ Token created successfully!")
    print()
    
    # Extract pool address from TokenCreated event
    token_created_event = token_factory.events.TokenCreated().process_receipt(receipt)
    if token_created_event:
        pool_address = token_created_event[0]['args']['poolAddress']
        creator = token_created_event[0]['args']['creator']
        
        print(f"📍 Pool Address: {pool_address}")
        print(f"👤 Creator: {creator}")
        print()
        
        # Check pool state
        print("🔍 Checking pool state...")
        pool = w3s.get_bonding_pool_contract(pool_address)
        
        kas_reserve = pool.functions.kasReserve().call()
        token_reserve = pool.functions.tokenReserve().call()
        gc_address = pool.functions.graduationController().call()
        
        print(f"   KAS Reserve: {Web3.from_wei(kas_reserve, 'ether')} KAS")
        print(f"   Token Reserve: {Web3.from_wei(token_reserve, 'ether')} tokens")
        print(f"   GraduationController: {gc_address}")
        
        # Verify GC is V8
        if gc_address.lower() == GC_V8.lower():
            print("   ✅ Correct GraduationController V8!")
        else:
            print(f"   ❌ WRONG GC! Expected {GC_V8}, got {gc_address}")
        
        # Calculate market cap (simplified: assume $0.05/KAS for testing)
        kas_usd_price = 0.05762
        market_cap_usd = float(Web3.from_wei(kas_reserve, 'ether')) * kas_usd_price
        
        print()
        print(f"💰 Market Cap Estimate: ${market_cap_usd:.2f} USD")
        
        if market_cap_usd >= 50:
            print("   ✅ Token is ELIGIBLE for graduation!")
            print()
            print("🎓 Ready to test graduation:")
            print(f"   1. Initiate: Pool.initiateGraduation()")
            print(f"   2. Complete: GC.completeGraduation({pool_address})")
        else:
            print("   ⚠️  Token needs more KAS to reach $50 threshold")
            needed_kas = (50 / kas_usd_price) - float(Web3.from_wei(kas_reserve, 'ether'))
            print(f"   💡 Buy ~{needed_kas:.2f} more KAS worth to graduate")
        
        print()
        print("="*80)
        print(f"🎯 POOL ADDRESS FOR TESTING: {pool_address}")
        print("="*80)
    else:
        print("❌ Could not extract pool address from receipt")
else:
    print(f"❌ Transaction failed! Status: {receipt['status']}")
    print(f"Gas used: {receipt['gasUsed']:,}")
