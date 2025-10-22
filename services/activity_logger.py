"""
Activity Logger Service
Creates Activity feed entries from trade events
"""

import logging
from datetime import datetime, timezone
from models import User, Token, Activity, db

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_activity_from_trade(trade_event, token=None):
    """
    Create activity feed entry from a trade event
    
    Args:
        trade_event: TradeEvent instance
        token: Token instance (optional, will query if not provided)
    
    Returns:
        Activity instance if created, None if user/token not found
    """
    try:
        # Find user by wallet address
        user = User.query.filter_by(wallet_address=trade_event.user_wallet_address.lower()).first()
        if not user:
            logger.debug(f"User not found for wallet {trade_event.user_wallet_address}, skipping activity log")
            return None
        
        # Get token if not provided
        if not token:
            token = Token.query.get(trade_event.token_id)
            if not token:
                logger.warning(f"Token not found for activity log: {trade_event.token_id}")
                return None
        
        # Create activity based on trade type
        activity_type = None
        title = None
        description = None
        
        if trade_event.trade_type == 'buy':
            activity_type = 'trade_buy'
            title = f"Bought {token.symbol}"
            description = f"Purchased {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS"
        
        elif trade_event.trade_type == 'sell':
            activity_type = 'trade_sell'
            title = f"Sold {token.symbol}"
            description = f"Sold {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS"
        
        elif trade_event.trade_type == 'dex_buy':
            activity_type = 'trade_dex_buy'
            title = f"Bought {token.symbol} on DEX"
            description = f"Purchased {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS via Kaspa Finance DEX"
        
        elif trade_event.trade_type == 'dex_sell':
            activity_type = 'trade_dex_sell'
            title = f"Sold {token.symbol} on DEX"
            description = f"Sold {trade_event.token_amount:,.0f} {token.symbol} for {trade_event.kas_amount:.2f} KAS via Kaspa Finance DEX"
        
        elif trade_event.trade_type == 'airdrop':
            activity_type = 'airdrop_received'
            title = f"Received {token.symbol} airdrop"
            description = f"Received {trade_event.token_amount:,.0f} {token.symbol} via airdrop"
        
        else:
            logger.debug(f"Unknown trade type for activity log: {trade_event.trade_type}")
            return None
        
        # Create activity entry
        activity = Activity(
            user_id=user.id,
            activity_type=activity_type,
            title=title,
            description=description,
            token_id=token.id,
            trade_id=None,  # TradeEvent doesn't map to Trade model
            created_at=trade_event.timestamp
        )
        
        db.session.add(activity)
        
        logger.debug(f"✅ Created activity log for {user.wallet_address[:10]}... ({activity_type})")
        
        return activity
        
    except Exception as e:
        logger.error(f"Error creating activity from trade: {str(e)}")
        return None


def create_activities_batch(trade_events, token):
    """
    Create activity entries for multiple trade events in batch
    
    Args:
        trade_events: List of TradeEvent instances
        token: Token instance
    
    Returns:
        int: Number of activities created
    """
    created_count = 0
    for trade_event in trade_events:
        result = create_activity_from_trade(trade_event, token=token)
        if result:
            created_count += 1
    
    logger.debug(f"✅ Created {created_count} activity entries for {token.symbol}")
    return created_count
