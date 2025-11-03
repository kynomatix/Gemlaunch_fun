#!/usr/bin/env python3
"""
Fix market cap decimal bug: Convert all market_cap values from 1e18 to 1e8 decimals.

This script fixes the bug where KAS amounts were incorrectly divided by 1e18 (Ethereum decimals)
instead of 1e8 (Kaspa decimals), making stored values 1e10 times too small.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Token
from services.web3_service import get_web3_service
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_market_caps():
    """Recalculate market caps for all non-graduated tokens from blockchain"""
    with app.app_context():
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        # Get all non-graduated tokens with contract addresses
        tokens = Token.query.filter(
            Token.is_graduated == False,
            Token.contract_address.isnot(None)
        ).all()
        
        logger.info(f"Found {len(tokens)} tokens to fix")
        
        fixed_count = 0
        error_count = 0
        
        for token in tokens:
            try:
                pool_address = token.liquidity_pool_address or token.contract_address
                pool_contract = web3_service.get_bonding_pool_contract(pool_address)
                
                # Read current reserves from blockchain with CORRECT decimals
                kas_reserve_wei = pool_contract.functions.virtualKasReserve().call()
                token_reserve_wei = pool_contract.functions.virtualTokenReserve().call()
                
                # CORRECT: Kaspa uses 8 decimals
                kas_reserve = float(kas_reserve_wei) / 1e8
                token_reserve = float(token_reserve_wei) / 1e8
                
                # Calculate price
                new_price = kas_reserve / token_reserve if token_reserve > 0 else 0
                
                # Store old values for comparison
                old_market_cap = token.current_market_cap
                old_ath = token.market_cap_ath
                
                # Update token with corrected values
                token.current_price = new_price
                token.kas_reserve = kas_reserve
                token.token_reserve = token_reserve_wei
                token.current_market_cap = kas_reserve
                
                # Reset ATH to current value if it was corrupted (too small)
                # If old ATH was < 0.01 KAS, it's likely corrupted, so reset to current
                if token.market_cap_ath is None or float(token.market_cap_ath) < 0.01:
                    token.market_cap_ath = kas_reserve
                    logger.info(f"✅ {token.symbol}: MC {old_market_cap:.8f} → {kas_reserve:.2f} KAS, ATH reset from {old_ath} to {kas_reserve:.2f}")
                else:
                    # Multiply old ATH by 1e10 to correct the decimal error
                    corrected_ath = float(token.market_cap_ath) * 1e10
                    # But cap it at current reserve if that's higher
                    token.market_cap_ath = max(corrected_ath, kas_reserve)
                    logger.info(f"✅ {token.symbol}: MC {old_market_cap:.8f} → {kas_reserve:.2f} KAS, ATH corrected to {token.market_cap_ath:.2f}")
                
                fixed_count += 1
                
                # Commit every 10 tokens to avoid losing progress
                if fixed_count % 10 == 0:
                    db.session.commit()
                    logger.info(f"Progress: {fixed_count}/{len(tokens)} tokens fixed")
                
            except Exception as e:
                logger.error(f"Error fixing {token.symbol}: {str(e)}")
                error_count += 1
                continue
        
        # Final commit
        db.session.commit()
        
        logger.info(f"\n✅ Backfill complete!")
        logger.info(f"   Fixed: {fixed_count}")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Total: {len(tokens)}")

if __name__ == '__main__':
    fix_market_caps()
