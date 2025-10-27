#!/usr/bin/env python3
"""
STF Error Debugger - Systematically find why SafeTransferFrom is failing
"""

import sys
from web3 import Web3
from eth_account import Account
import json

# Configuration
RPC_URL = "https://rpc.kasplextest.xyz"
CHAIN_ID = 167012

# Contract Addresses
GRADUATION_CONTROLLER_V6 = "0xBbfdF7341aaF104D259876972844EBF9795b9C4C"
TOKEN_FACTORY_V9 = "0xB4D21bD000275F58A7180502Af5215fc4adE9984"
ORACLE_ADDRESS = "0x5f837F62744D4d80Fc79C3A5346B4A228956914E"

# ABIs
POOL_ABI = [
    {"inputs": [{"type": "address", "name": "account"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address", "name": "owner"}, {"type": "address", "name": "spender"}], "name": "allowance", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduating", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduated", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduationController", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduationOracle", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "paused", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
]

GC_ABI = [
    {"inputs": [{"type": "address", "name": "tokenAddress"}], "name": "graduationSnapshots", "outputs": [
        {"type": "address", "name": "poolContract"},
        {"type": "uint256", "name": "kasLiquidity"},
        {"type": "uint256", "name": "tokenLiquidity"},
        {"type": "uint256", "name": "snapshotTime"},
        {"type": "bool", "name": "lpCreated"}
    ], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address", "name": "tokenAddress"}], "name": "completeGraduation", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}")

def print_check(passed, message, details=""):
    symbol = "✅" if passed else "❌"
    print(f"{symbol} {message}")
    if details:
        print(f"   → {details}")

def format_tokens(amount, decimals=18):
    return f"{amount / 10**decimals:,.2f}"

def debug_token(token_address):
    """Run full diagnostic on a token"""
    print(f"\n{'='*80}")
    print(f"🔍 DEBUGGING STF ERROR FOR: {token_address}")
    print(f"{'='*80}\n")
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print("❌ Cannot connect to RPC!")
        return
    
    token_address = Web3.to_checksum_address(token_address)
    pool = w3.eth.contract(address=token_address, abi=POOL_ABI)
    
    # Check 1: Basic State
    print_header("1. POOL BASIC STATE")
    
    try:
        graduating = pool.functions.graduating().call()
        graduated = pool.functions.graduated().call()
        gc_address = pool.functions.graduationController().call()
        oracle_address = pool.functions.graduationOracle().call()
        
        print_check(graduating, f"Graduating: {graduating}")
        print_check(not graduated, f"Graduated: {graduated}", "Should be False")
        print_check(gc_address.lower() == GRADUATION_CONTROLLER_V6.lower(), 
                   f"GC: {gc_address}", f"Expected: {GRADUATION_CONTROLLER_V6}")
        print_check(oracle_address.lower() == ORACLE_ADDRESS.lower(),
                   f"Oracle: {oracle_address}", f"Expected: {ORACLE_ADDRESS}")
    except Exception as e:
        print_check(False, f"Error: {e}")
        return
    
    # Check 2: Balances
    print_header("2. TOKEN BALANCES")
    
    try:
        total_supply = pool.functions.totalSupply().call()
        pool_balance = pool.functions.balanceOf(token_address).call()
        gc_balance = pool.functions.balanceOf(gc_address).call()
        expected_transfer = total_supply // 4
        
        print(f"📊 Total Supply: {format_tokens(total_supply)}")
        print(f"📊 Pool Balance: {format_tokens(pool_balance)}")
        print(f"📊 GC Balance: {format_tokens(gc_balance)}")
        print(f"📊 Expected Transfer (25%): {format_tokens(expected_transfer)}")
        
        print_check(pool_balance >= expected_transfer, 
                   f"Pool has enough tokens: {pool_balance >= expected_transfer}",
                   f"Need {format_tokens(expected_transfer)}, have {format_tokens(pool_balance)}")
    except Exception as e:
        print_check(False, f"Error: {e}")
        return
    
    # Check 3: Allowance
    print_header("3. TOKEN ALLOWANCE")
    
    try:
        allowance = pool.functions.allowance(token_address, gc_address).call()
        
        print(f"📊 Current Allowance: {format_tokens(allowance)}")
        print(f"📊 Required: {format_tokens(expected_transfer)}")
        
        print_check(allowance >= expected_transfer,
                   f"Sufficient allowance: {allowance >= expected_transfer}",
                   f"Need {format_tokens(expected_transfer)}, have {format_tokens(allowance)}")
    except Exception as e:
        print_check(False, f"Error: {e}")
    
    # Check 4: GC Snapshot
    print_header("4. GRADUATION CONTROLLER SNAPSHOT")
    
    try:
        gc = w3.eth.contract(address=Web3.to_checksum_address(GRADUATION_CONTROLLER_V6), abi=GC_ABI)
        snapshot = gc.functions.graduationSnapshots(token_address).call()
        
        pool_contract, kas_liq, token_liq, snapshot_time, lp_created = snapshot
        
        print_check(pool_contract != "0x0000000000000000000000000000000000000000",
                   f"Snapshot exists: {pool_contract != '0x0000000000000000000000000000000000000000'}")
        print(f"📊 KAS Liquidity: {kas_liq / 1e18:.6f} KAS")
        print(f"📊 Token Liquidity: {format_tokens(token_liq)}")
        print(f"📊 Snapshot Time: {snapshot_time}")
        print_check(not lp_created, f"LP Created: {lp_created}", "Should be False")
    except Exception as e:
        print_check(False, f"Error reading snapshot: {e}")
    
    # Check 5: Transaction Simulation
    print_header("5. TRANSACTION SIMULATION (THE CRITICAL TEST)")
    
    try:
        gc = w3.eth.contract(address=Web3.to_checksum_address(GRADUATION_CONTROLLER_V6), abi=GC_ABI)
        
        tx = gc.functions.completeGraduation(token_address).build_transaction({
            'from': ORACLE_ADDRESS,
            'gas': 0,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(ORACLE_ADDRESS),
        })
        
        gas = w3.eth.estimate_gas(tx)
        print_check(True, "✅ TRANSACTION WOULD SUCCEED!")
        print(f"   Gas estimate: {gas:,}")
    except Exception as e:
        error_str = str(e)
        print_check(False, "❌ TRANSACTION WOULD FAIL!")
        print(f"   Error: {error_str}")
        
        # Decode error
        if "STF" in error_str or "0x" in error_str:
            print(f"\n   💡 This is the SafeTransferFrom error you're seeing!")
            print(f"   💡 The token transfer is being blocked during completeGraduation()")
    
    # Final Verdict
    print_header("🏁 FINAL VERDICT")
    
    print("\nRun this diagnostic to see the EXACT failure point.")
    print("The 'TRANSACTION SIMULATION' section shows if it would work or fail.\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_token(sys.argv[1])
    else:
        # Default to $CHIM
        debug_token("0x8c4102cce3b6d9461ef5aa7a845172dd2f479eca")
