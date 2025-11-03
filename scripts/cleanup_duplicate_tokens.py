#!/usr/bin/env python3
"""
Database cleanup script for duplicate tokens and corrupted ATH values

This script:
1. Hides old duplicate token versions by setting is_visible=false
2. Resets corrupted ATH values for tokens deployed on Nov 3, 2025
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone

def get_db_connection():
    """Get database connection from environment"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)

def cleanup_duplicate_tokens(conn):
    """Hide old duplicate token versions"""
    
    print("=" * 80)
    print("DUPLICATE TOKEN CLEANUP")
    print("=" * 80)
    
    # Duplicate tokens to hide (old versions)
    duplicates_to_hide = [
        {'id': 55, 'symbol': 'GRUMP', 'keep_id': 108, 'keep_contract': '0x3da7...'},
        {'id': 58, 'symbol': 'DUMP', 'keep_id': 106, 'keep_contract': '0x2264...'},
        {'id': 69, 'symbol': 'KAMI', 'keep_id': 107, 'keep_contract': '0x5e51...'},
        {'id': 87, 'symbol': 'KREX', 'keep_id': 103, 'keep_contract': '0x1a04...'},
        {'id': 72, 'symbol': 'KTR', 'keep_id': 105, 'keep_contract': '0xb87f...'},
        {'id': 68, 'symbol': 'SPK', 'keep_id': 104, 'keep_contract': '0x3763...'},
    ]
    
    cursor = conn.cursor()
    hidden_count = 0
    already_hidden_count = 0
    
    for dup in duplicates_to_hide:
        # Check current status
        cursor.execute(
            "SELECT id, symbol, name, contract_address, is_visible, created_at FROM token WHERE id = %s",
            (dup['id'],)
        )
        token = cursor.fetchone()
        
        if not token:
            print(f"⚠️  Token ID {dup['id']} ({dup['symbol']}) not found - skipping")
            continue
        
        token_id, symbol, name, contract, is_visible, created_at = token
        
        if not is_visible:
            print(f"ℹ️  Token ID {token_id} ({symbol}) already hidden - no action needed")
            already_hidden_count += 1
            continue
        
        # Verify it's the right token by checking symbol
        if symbol != dup['symbol']:
            print(f"⚠️  Token ID {token_id} symbol mismatch: expected {dup['symbol']}, got {symbol} - skipping")
            continue
        
        print(f"\n🔄 Hiding duplicate token:")
        print(f"   ID: {token_id}")
        print(f"   Symbol: {symbol}")
        print(f"   Name: {name}")
        print(f"   Contract: {contract}")
        print(f"   Created: {created_at}")
        print(f"   Keeping: ID {dup['keep_id']} ({dup['keep_contract']})")
        
        # Hide the token
        cursor.execute(
            "UPDATE token SET is_visible = false WHERE id = %s",
            (token_id,)
        )
        hidden_count += 1
    
    # Commit the changes
    conn.commit()
    
    if hidden_count > 0:
        print(f"\n✅ Successfully hidden {hidden_count} duplicate tokens")
    if already_hidden_count > 0:
        print(f"✅ {already_hidden_count} tokens were already hidden")
    if hidden_count == 0 and already_hidden_count == 0:
        print(f"\n✅ No tokens needed to be hidden")
    
    return hidden_count, already_hidden_count

def fix_corrupted_ath_values(conn):
    """Reset corrupted ATH values for tokens deployed on Nov 3, 2025"""
    
    print("\n" + "=" * 80)
    print("CORRUPTED ATH VALUE CLEANUP")
    print("=" * 80)
    
    cursor = conn.cursor()
    
    # Find tokens with corrupted ATH values
    cursor.execute("""
        SELECT id, symbol, name, created_at, current_market_cap, market_cap_ath
        FROM token
        WHERE created_at >= '2025-11-03' AND market_cap_ath = 1000
        ORDER BY id
    """)
    
    corrupted_tokens = cursor.fetchall()
    
    print(f"\nFound {len(corrupted_tokens)} tokens with corrupted ATH values")
    
    fixed_count = 0
    
    for token in corrupted_tokens:
        token_id, symbol, name, created_at, current_market_cap, market_cap_ath = token
        
        old_ath = float(market_cap_ath) if market_cap_ath else 0
        new_ath = float(current_market_cap) if current_market_cap else 0
        
        print(f"\n🔄 Fixing ATH for token:")
        print(f"   ID: {token_id}")
        print(f"   Symbol: {symbol}")
        print(f"   Name: {name}")
        print(f"   Created: {created_at}")
        print(f"   Old ATH: {old_ath} KAS")
        print(f"   New ATH (current market cap): {new_ath} KAS")
        
        # Set ATH to current market cap
        cursor.execute(
            "UPDATE token SET market_cap_ath = current_market_cap WHERE id = %s",
            (token_id,)
        )
        fixed_count += 1
    
    # Commit the changes
    conn.commit()
    
    if fixed_count > 0:
        print(f"\n✅ Successfully fixed {fixed_count} corrupted ATH values")
    else:
        print(f"\n✅ No corrupted ATH values found")
    
    return fixed_count

def main():
    """Main cleanup function"""
    
    print("\n" + "=" * 80)
    print("DATABASE CLEANUP SCRIPT")
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    try:
        conn = get_db_connection()
        
        # Step 1: Hide duplicate tokens
        hidden_count, already_hidden_count = cleanup_duplicate_tokens(conn)
        
        # Step 2: Fix corrupted ATH values
        fixed_count = fix_corrupted_ath_values(conn)
        
        conn.close()
        
        # Summary
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"✅ Duplicate tokens hidden: {hidden_count}")
        print(f"ℹ️  Duplicate tokens already hidden: {already_hidden_count}")
        print(f"✅ Corrupted ATH values fixed: {fixed_count}")
        print(f"\nCompleted at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 80 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
