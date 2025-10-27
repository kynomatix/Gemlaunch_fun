#!/usr/bin/env python3
"""
Deep STF Diagnostic - Find the EXACT reason SafeTransferFrom fails

This checks the actual _update() function logic to see what's blocking the transfer
"""

from web3 import Web3

RPC_URL = "https://rpc.kasplextest.xyz"
CHIM = "0x8c4102cce3b6d9461ef5aa7a845172dd2f479eca"
GC_V6 = "0xBbfdF7341aaF104D259876972844EBF9795b9C4C"

# Extended ABI to check exemptions and wallet cap
POOL_ABI = [
    {"inputs": [{"type": "address", "name": "account"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduationController", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "owner", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "airdropTreasury", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduationOracle", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "graduated", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "isVestingContract", "outputs": [{"type": "bool"}], "stateMutability": "view", "type": "function"},
]

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    chim = Web3.to_checksum_address(CHIM)
    gc = Web3.to_checksum_address(GC_V6)
    
    pool = w3.eth.contract(address=chim, abi=POOL_ABI)
    
    print("\n" + "="*80)
    print("🔬 DEEP DIVE: Why is SafeTransferFrom Blocked?")
    print("="*80 + "\n")
    
    # Get all the exemption addresses
    print("📋 CHECKING _update() EXEMPTION LOGIC\n")
    
    gc_from_pool = pool.functions.graduationController().call()
    owner = pool.functions.owner().call()
    airdrop_treasury = pool.functions.airdropTreasury().call()
    oracle = pool.functions.graduationOracle().call()
    graduated = pool.functions.graduated().call()
    
    print(f"Transfer: {chim} → {gc}")
    print(f"\nExempted Addresses (from _update() logic):")
    print(f"  1. address(this): {chim}")
    print(f"  2. airdropTreasury: {airdrop_treasury}")
    print(f"  3. graduationOracle: {oracle}")
    print(f"  4. graduationController: {gc_from_pool}")
    print(f"  5. owner(): {owner}")
    print(f"  6. graduated flag: {graduated}")
    
    # Check if GC matches
    gc_matches = gc_from_pool.lower() == gc.lower()
    print(f"\n🔍 GC Address Match: {'✅ YES' if gc_matches else '❌ NO'}")
    print(f"   Pool's GC: {gc_from_pool}")
    print(f"   Actual GC: {gc}")
    
    if not gc_matches:
        print(f"\n🚨 ROOT CAUSE FOUND: Pool's graduationController != actual GC!")
        print(f"   The exemption checks `to != graduationController`")
        print(f"   But graduationController = {gc_from_pool}")
        print(f"   So {gc} is NOT exempt!")
        return
    
    # Check wallet cap calculation
    print(f"\n📊 WALLET CAP CALCULATION")
    
    total_supply = pool.functions.totalSupply().call()
    gc_balance = pool.functions.balanceOf(gc).call()
    transfer_amount = total_supply // 4  # 25%
    
    max_wallet = total_supply * 10 // 100  # 10%
    gc_balance_after = gc_balance + transfer_amount
    
    print(f"   Total Supply: {total_supply / 1e18:,.0f}")
    print(f"   Max Wallet (10%): {max_wallet / 1e18:,.0f}")
    print(f"   GC Current Balance: {gc_balance / 1e18:,.0f}")
    print(f"   Transfer Amount (25%): {transfer_amount / 1e18:,.0f}")
    print(f"   GC Balance After: {gc_balance_after / 1e18:,.0f}")
    
    would_exceed = gc_balance_after > max_wallet
    print(f"\n   Would exceed cap: {'❌ YES' if would_exceed else '✅ NO'}")
    
    if would_exceed:
        print(f"\n🔍 CHECKING IF GC IS EXEMPT...")
        
        # The _update() function checks these conditions for exemption:
        checks = {
            "to != address(0)": gc != "0x0000000000000000000000000000000000000000",
            "to != address(this)": gc.lower() != chim.lower(),
            "to != airdropTreasury": gc.lower() != airdrop_treasury.lower(),
            "to != graduationOracle": gc.lower() != oracle.lower(),
            "to != graduationController": gc.lower() != gc_from_pool.lower(),
            "to != owner()": gc.lower() != owner.lower(),
            "!graduated": not graduated,
        }
        
        print(f"\n   Exemption checks (if ANY is False, GC is exempt):")
        for check, result in checks.items():
            symbol = "✅" if result else "❌"
            print(f"   {symbol} {check}: {result}")
        
        all_true = all(checks.values())
        
        if all_true:
            print(f"\n🚨 ROOT CAUSE FOUND: ALL CHECKS PASS → WALLET CAP IS ENFORCED!")
            print(f"   The _update() function will enforce the 10% cap")
            print(f"   GC is NOT exempt because none of the exemption conditions match")
            print(f"   25% transfer > 10% cap → SafeTransferFrom FAILS")
            print(f"\n💡 SOLUTION: Add 'to != graduationController' exemption to _update()")
        else:
            print(f"\n✅ GC SHOULD BE EXEMPT (at least one check is False)")
            print(f"   The wallet cap check should be skipped")
            print(f"   STF error must be from something else...")
    else:
        print(f"\n✅ Transfer wouldn't exceed cap anyway")
        print(f"   STF error must be from something OTHER than wallet cap")
    
    print("\n" + "="*80)
    print("🎯 DIAGNOSIS COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
