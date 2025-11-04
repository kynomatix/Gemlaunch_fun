"""
User Stats Updater Service
Updates User model statistics from trade events
"""

import logging
from decimal import Decimal
from models import User, db

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def update_user_stats_from_trade(trade_event, kas_amount):
    """
    Update user statistics from a trade event
    
    Args:
        trade_event: TradeEvent instance
        kas_amount: Decimal amount of KAS traded
    
    Returns:
        User instance if updated, None if user not found
    """
    try:
        # Find user by wallet address
        user = User.query.filter_by(wallet_address=trade_event.user_wallet_address.lower()).first()
        if not user:
            logger.debug(f"User not found for wallet {trade_event.user_wallet_address}, skipping stats update")
            return None
        
        # Update trade count (only for buy/sell trades, not airdrops)
        if trade_event.trade_type in ('buy', 'sell', 'dex_buy', 'dex_sell'):
            user.total_trades_count = (user.total_trades_count or 0) + 1
            user.total_trading_volume = (user.total_trading_volume or 0) + kas_amount
        
        logger.debug(f"✅ Updated user stats for {user.wallet_address[:10]}... ({trade_event.trade_type})")
        
        return user
        
    except Exception as e:
        logger.error(f"Error updating user stats from trade: {str(e)}")
        return None


def update_user_stats_batch(trade_events_with_amounts):
    """
    Update user stats for multiple trade events in batch
    
    Args:
        trade_events_with_amounts: List of (TradeEvent, kas_amount) tuples
    
    Returns:
        int: Number of users updated
    """
    # Group trades by user wallet
    user_trades = {}
    for trade_event, kas_amount in trade_events_with_amounts:
        wallet = trade_event.user_wallet_address.lower()
        if wallet not in user_trades:
            user_trades[wallet] = {'count': 0, 'volume': 0}
        
        # Only count buy/sell trades, not airdrops
        if trade_event.trade_type in ('buy', 'sell', 'dex_buy', 'dex_sell'):
            user_trades[wallet]['count'] += 1
            user_trades[wallet]['volume'] += kas_amount
    
    # Update users
    updated_count = 0
    for wallet, stats in user_trades.items():
        user = User.query.filter_by(wallet_address=wallet).first()
        if user:
            # Calculate points based on cumulative volume thresholds crossed
            # Use Decimal to avoid floating point precision errors
            old_volume = user.total_trading_volume or Decimal(0)
            new_volume = old_volume + stats['volume']
            
            # Points = floor(new_total / 100) - floor(old_total / 100)
            # Use Decimal division to ensure precise threshold detection
            old_points_threshold = int(old_volume / Decimal(100))
            new_points_threshold = int(new_volume / Decimal(100))
            points_to_add = new_points_threshold - old_points_threshold
            
            # Update stats
            user.total_trades_count = (user.total_trades_count or 0) + stats['count']
            user.total_trading_volume = (user.total_trading_volume or 0) + stats['volume']
            
            # Award GEM points if threshold crossed
            if points_to_add > 0:
                user.gem_points = (user.gem_points or 0) + points_to_add
                logger.debug(f"  💎 Awarded {points_to_add} GEM points ({float(old_volume):.2f} → {float(new_volume):.2f} KAS)")
            
            updated_count += 1
    
    logger.debug(f"✅ Updated stats for {updated_count} users in batch")
    return updated_count
