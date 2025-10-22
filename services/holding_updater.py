"""
Holding Updater Service
Updates Position model for FTX-style cost basis tracking
"""

import logging
from decimal import Decimal
from models import User, Position, db

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def update_holding_from_trade(trade_event):
    """
    Update position/holding cost basis from a trade event
    
    Args:
        trade_event: TradeEvent instance
    
    Returns:
        Position instance if updated, None if user not found
    """
    try:
        # Find user by wallet address
        user = User.query.filter_by(wallet_address=trade_event.user_wallet_address.lower()).first()
        if not user:
            logger.debug(f"User not found for wallet {trade_event.user_wallet_address}, skipping holding update")
            return None
        
        # Get or create position
        position = Position.query.filter_by(
            user_id=user.id,
            token_id=trade_event.token_id
        ).first()
        
        if not position:
            position = Position(
                user_id=user.id,
                token_id=trade_event.token_id,
                qty_remaining=0,
                cost_basis_kas=0,
                avg_entry_price_kas=0,
                realized_pnl_kas=0
            )
            db.session.add(position)
        
        # Update position based on trade type
        if trade_event.trade_type in ('buy', 'dex_buy', 'airdrop'):
            # Buy or airdrop: Increase position
            old_qty = position.qty_remaining
            old_cost_basis = position.cost_basis_kas
            
            # Calculate new position
            new_qty = old_qty + trade_event.token_amount
            new_cost_basis = old_cost_basis + trade_event.kas_amount  # For airdrops, kas_amount = 0
            
            position.qty_remaining = new_qty
            position.cost_basis_kas = new_cost_basis
            
            # Update average entry price (handle division by zero)
            if new_qty > 0:
                position.avg_entry_price_kas = new_cost_basis / new_qty
            else:
                position.avg_entry_price_kas = 0
            
            logger.debug(f"✅ Increased position for {user.wallet_address[:10]}... ({trade_event.trade_type}): +{trade_event.token_amount} tokens")
        
        elif trade_event.trade_type in ('sell', 'dex_sell'):
            # Sell: Decrease position and realize PnL
            old_qty = position.qty_remaining
            old_cost_basis = position.cost_basis_kas
            
            if old_qty == 0:
                logger.warning(f"Sell trade for user with zero position: {user.wallet_address[:10]}...")
                return position
            
            # Calculate proportion sold
            sell_ratio = trade_event.token_amount / old_qty if old_qty > 0 else 0
            cost_basis_sold = old_cost_basis * sell_ratio
            
            # Calculate realized PnL
            realized_pnl = trade_event.kas_amount - cost_basis_sold
            position.realized_pnl_kas = (position.realized_pnl_kas or 0) + realized_pnl
            
            # Update position
            position.qty_remaining = old_qty - trade_event.token_amount
            position.cost_basis_kas = old_cost_basis - cost_basis_sold
            
            # Average entry price remains the same (it's per-token, not total)
            
            logger.debug(f"✅ Decreased position for {user.wallet_address[:10]}... ({trade_event.trade_type}): -{trade_event.token_amount} tokens, PnL: {realized_pnl:.4f} KAS")
        
        return position
        
    except Exception as e:
        logger.error(f"Error updating holding from trade: {str(e)}")
        return None


def update_holdings_batch(trade_events):
    """
    Update holdings for multiple trade events in batch
    
    Args:
        trade_events: List of TradeEvent instances
    
    Returns:
        int: Number of positions updated
    """
    updated_count = 0
    for trade_event in trade_events:
        result = update_holding_from_trade(trade_event)
        if result:
            updated_count += 1
    
    logger.debug(f"✅ Updated {updated_count} positions in batch")
    return updated_count
