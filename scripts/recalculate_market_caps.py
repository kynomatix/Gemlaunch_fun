#!/usr/bin/env python3
"""
Recalculate Market Caps Script
Fixes USD/KAS unit mismatch in the database by:
1. Setting current_market_cap = kas_reserve for non-graduated tokens
2. Calculating market_cap_ath from TradeEvent history
"""

import sys
import os
from decimal import Decimal

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Token, TradeEvent
from sqlalchemy import func

def recalculate_market_caps():
    """Recalculate market caps for all non-graduated tokens"""
    
    with app.app_context():
        print("=" * 80)
        print("MARKET CAP RECALCULATION SCRIPT")
        print("=" * 80)
        print()
        
        # Query all non-graduated tokens
        non_graduated_tokens = Token.query.filter_by(is_graduated=False).all()
        
        print(f"Found {len(non_graduated_tokens)} non-graduated tokens to process")
        print()
        
        # Track statistics
        total_updated = 0
        total_skipped = 0
        
        for token in non_graduated_tokens:
            try:
                # Store old values for logging
                old_current_mc = float(token.current_market_cap) if token.current_market_cap else 0
                old_ath_mc = float(token.market_cap_ath) if token.market_cap_ath else 0
                
                # Step 1: Set current_market_cap = kas_reserve
                new_current_mc = token.kas_reserve if token.kas_reserve else Decimal('0')
                token.current_market_cap = new_current_mc
                
                # Step 2: Calculate market_cap_ath from TradeEvent history
                # Find the maximum kas_amount from all trades for this token
                max_kas_result = db.session.query(
                    func.max(TradeEvent.kas_amount)
                ).filter(
                    TradeEvent.token_id == token.id
                ).scalar()
                
                max_kas_from_trades = max_kas_result if max_kas_result else Decimal('0')
                
                # Step 3: Set market_cap_ath = MAX(max_kas_from_trades, current_market_cap)
                # ATH can't be less than current market cap
                new_ath_mc = max(max_kas_from_trades, new_current_mc)
                token.market_cap_ath = new_ath_mc
                
                # Determine if changes were made
                current_mc_changed = abs(float(new_current_mc) - old_current_mc) > 0.00000001
                ath_mc_changed = abs(float(new_ath_mc) - old_ath_mc) > 0.00000001
                
                if current_mc_changed or ath_mc_changed:
                    total_updated += 1
                    print(f"✅ Updated {token.symbol} (ID: {token.id})")
                    if current_mc_changed:
                        print(f"   Current Market Cap: {old_current_mc:.8f} KAS → {float(new_current_mc):.8f} KAS")
                    if ath_mc_changed:
                        print(f"   ATH Market Cap: {old_ath_mc:.8f} KAS → {float(new_ath_mc):.8f} KAS")
                    print(f"   KAS Reserve: {float(token.kas_reserve):.8f} KAS")
                    print(f"   Max KAS from Trades: {float(max_kas_from_trades):.8f} KAS")
                    print()
                else:
                    total_skipped += 1
                
            except Exception as e:
                print(f"❌ Error processing {token.symbol} (ID: {token.id}): {str(e)}")
                print()
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print("=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print(f"Total tokens processed: {len(non_graduated_tokens)}")
            print(f"Tokens updated: {total_updated}")
            print(f"Tokens skipped (no changes): {total_skipped}")
            print()
            print("✅ All changes committed successfully!")
            print()
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {str(e)}")
            return False
        
        # Show specific token results (HASH and PHNT)
        print("=" * 80)
        print("SPECIFIC TOKEN RESULTS")
        print("=" * 80)
        print()
        
        for symbol in ['HASH', 'PHNT']:
            token = Token.query.filter_by(symbol=symbol, is_graduated=False).first()
            if token:
                print(f"Token: {token.symbol} (ID: {token.id})")
                print(f"  Name: {token.name}")
                print(f"  Current Market Cap: {float(token.current_market_cap):.8f} KAS")
                print(f"  Market Cap ATH: {float(token.market_cap_ath):.8f} KAS")
                print(f"  KAS Reserve: {float(token.kas_reserve):.8f} KAS")
                print(f"  Is Graduated: {token.is_graduated}")
                
                # Show trade count
                trade_count = TradeEvent.query.filter_by(token_id=token.id).count()
                print(f"  Total Trades: {trade_count}")
                print()
            else:
                print(f"Token {symbol} not found or is graduated")
                print()
        
        return True

if __name__ == "__main__":
    success = recalculate_market_caps()
    sys.exit(0 if success else 1)
