"""
Backfill User Statistics Script

This script recalculates user statistics from actual database records:
- total_tokens_created: Count of tokens created by user
- total_trading_volume: Sum of KAS traded (buy + sell)
- total_trades_count: Count of trades executed

Usage:
    python scripts/backfill_user_stats.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from models import User, Token, TradeEvent
from sqlalchemy import func
from decimal import Decimal

def backfill_user_stats():
    """Recalculate all user statistics from actual database records"""
    
    with app.app_context():
        print("=" * 60)
        print("BACKFILLING USER STATISTICS")
        print("=" * 60)
        
        users = User.query.all()
        print(f"\nFound {len(users)} users to process")
        
        updated_count = 0
        
        for user in users:
            print(f"\n📍 Processing: {user.wallet_address[:10]}...")
            
            # 1. Calculate total_tokens_created
            tokens_created = Token.query.filter_by(
                creator_id=user.id,
                is_visible=True
            ).count()
            
            # 2. Calculate total_trading_volume and total_trades_count
            # TradeEvent uses wallet_address, not user_id
            trades = TradeEvent.query.filter_by(
                user_wallet_address=user.wallet_address
            ).all()
            
            total_volume = Decimal('0')
            trades_count = len(trades)
            
            for trade in trades:
                # Add KAS amount for both buys and sells
                total_volume += Decimal(str(trade.kas_amount or 0))
            
            # Update user record
            old_tokens = user.total_tokens_created or 0
            old_volume = float(user.total_trading_volume or 0)
            old_trades = user.total_trades_count or 0
            
            user.total_tokens_created = tokens_created
            user.total_trading_volume = total_volume
            user.total_trades_count = trades_count
            
            # Show changes if any
            if (tokens_created != old_tokens or 
                float(total_volume) != old_volume or 
                trades_count != old_trades):
                
                print(f"   ✅ Updated:")
                if tokens_created != old_tokens:
                    print(f"      Tokens: {old_tokens} → {tokens_created}")
                if float(total_volume) != old_volume:
                    print(f"      Volume: ${old_volume:,.2f} → ${float(total_volume):,.2f}")
                if trades_count != old_trades:
                    print(f"      Trades: {old_trades} → {trades_count}")
                
                updated_count += 1
            else:
                print(f"   ⚪ No changes needed")
        
        # Commit all changes
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"✅ BACKFILL COMPLETE")
        print(f"   Updated {updated_count} users")
        print("=" * 60)
        
        # Show top 10 users by GEM points
        print("\n📊 TOP 10 LEADERBOARD:")
        print("-" * 60)
        top_users = User.query.order_by(User.gem_points.desc()).limit(10).all()
        
        for idx, u in enumerate(top_users, 1):
            print(f"{idx:2d}. {u.wallet_address[:10]}... - {u.gem_points:,} GEM")
            print(f"    Tokens: {u.total_tokens_created} | "
                  f"Volume: ${float(u.total_trading_volume or 0):,.0f} | "
                  f"Trades: {u.total_trades_count}")
        
        print("-" * 60)

if __name__ == '__main__':
    backfill_user_stats()
