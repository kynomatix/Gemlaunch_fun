"""One-time script to backfill MEGA's historical DEX trades"""
import sys
from app import app, db
from models import Token
from services.web3_service import get_web3_service
from services.event_indexer import process_dex_pool_events

def backfill_mega():
    with app.app_context():
        # Get MEGA token
        mega = Token.query.filter_by(symbol='MEGA').first()
        if not mega:
            print("❌ MEGA token not found")
            return
        
        if not mega.dex_pool_address:
            print("❌ MEGA has no DEX pool address")
            return
        
        print(f"📊 MEGA Token:")
        print(f"  Pool: {mega.dex_pool_address}")
        print(f"  Graduation TX: {mega.graduation_tx}")
        
        # Get graduation block
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        if mega.graduation_tx:
            tx_receipt = w3.eth.get_transaction_receipt(mega.graduation_tx)
            graduation_block = tx_receipt['blockNumber']
            print(f"  Graduation block: {graduation_block}")
        else:
            print("  ⚠️ No graduation TX - using block 0")
            graduation_block = 0
        
        # Get current block
        current_block = w3.eth.block_number
        print(f"\nCurrent block: {current_block}")
        
        # Backfill from graduation block to current block
        print(f"\n🔍 Backfilling DEX trades from block {graduation_block} to {current_block}...")
        result = process_dex_pool_events(
            pool_address=mega.dex_pool_address,
            from_block=graduation_block,
            to_block=current_block
        )
        
        if result['success']:
            stats = result['stats']
            print(f"\n✅ Backfill complete:")
            print(f"  DEX buys: {stats['dex_buys']}")
            print(f"  DEX sells: {stats['dex_sells']}")
            print(f"  Duplicates skipped: {stats['duplicates']}")
            print(f"  Errors: {stats['errors']}")
        else:
            print(f"\n❌ Backfill failed: {result.get('error')}")

if __name__ == '__main__':
    backfill_mega()
