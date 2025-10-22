"""
Engagement Calculator Service
Calculates holding milestones and awards community points for PRO tokens
Real-time trade engagement tracking + daily milestone awards
"""

import logging
from datetime import datetime, timezone
from app import db
from models import User, Token, TokenEngagement
from services.token_service import TokenService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def update_engagement_from_trade(trade_event, kas_amount, token=None):
    """
    Update token engagement metrics from a trade event (real-time)
    
    Args:
        trade_event: TradeEvent instance
        kas_amount: Decimal amount of KAS traded
        token: Token instance (optional, will query if not provided)
    
    Returns:
        TokenEngagement instance if updated, None if not applicable
    """
    try:
        # Get token if not provided
        if not token:
            token = Token.query.get(trade_event.token_id)
            if not token:
                logger.warning(f"Token not found for engagement update: {trade_event.token_id}")
                return None
        
        # Only track engagement for PRO tokens
        if not TokenService.is_pro_token(token):
            return None
        
        # Find user by wallet address
        user = User.query.filter_by(wallet_address=trade_event.user_wallet_address.lower()).first()
        if not user:
            logger.debug(f"User not found for wallet {trade_event.user_wallet_address}, skipping engagement")
            return None
        
        # Get or create engagement record
        engagement = TokenEngagement.get_or_create(user.id, token.id)
        
        # Update engagement based on trade type
        if trade_event.trade_type in ('buy', 'dex_buy'):
            engagement.buy_count = (engagement.buy_count or 0) + 1
            engagement.trades_count = (engagement.trades_count or 0) + 1
            engagement.total_traded_volume = (engagement.total_traded_volume or 0) + kas_amount
            engagement.community_points = (engagement.community_points or 0) + 10  # 10 points per buy
            
            # Update first acquired timestamp if this is their first purchase
            if not engagement.first_acquired_at:
                engagement.first_acquired_at = trade_event.timestamp
        
        elif trade_event.trade_type in ('sell', 'dex_sell'):
            engagement.sell_count = (engagement.sell_count or 0) + 1
            engagement.trades_count = (engagement.trades_count or 0) + 1
            engagement.total_traded_volume = (engagement.total_traded_volume or 0) + kas_amount
            engagement.community_points = (engagement.community_points or 0) + 5  # 5 points per sell
        
        elif trade_event.trade_type == 'airdrop':
            # Airdrops: Update first acquired timestamp but don't add to trade count
            # Airdrops are rewards for engagement, not trades
            if not engagement.first_acquired_at:
                engagement.first_acquired_at = trade_event.timestamp
        
        # Update last activity timestamp for all trade types
        engagement.last_activity_at = trade_event.timestamp
        
        logger.debug(f"✅ Updated engagement for {user.wallet_address[:10]}... on {token.symbol} ({trade_event.trade_type})")
        
        return engagement
        
    except Exception as e:
        logger.error(f"Error updating engagement from trade: {str(e)}")
        return None


def update_engagement_batch(trade_events_with_amounts, token):
    """
    Update engagement for multiple trade events in batch
    
    Args:
        trade_events_with_amounts: List of (TradeEvent, kas_amount) tuples
        token: Token instance
    
    Returns:
        int: Number of engagement records updated
    """
    if not TokenService.is_pro_token(token):
        return 0
    
    updated_count = 0
    for trade_event, kas_amount in trade_events_with_amounts:
        result = update_engagement_from_trade(trade_event, kas_amount, token=token)
        if result:
            updated_count += 1
    
    logger.debug(f"✅ Updated {updated_count} engagement records for {token.symbol}")
    return updated_count


def calculate_diamond_hands_score(buy_count, sell_count):
    """
    Calculate diamond hands score (0-100) based on buy/sell ratio
    
    Rules:
    - Only buyers (no sells): 100 points
    - 10:1 buy/sell ratio: 90 points
    - 5:1 buy/sell ratio: 80 points
    - 2:1 buy/sell ratio: 60 points
    - 1:1 buy/sell ratio: 40 points
    - More sells than buys: 20 points
    """
    if buy_count == 0:
        return 0
    
    if sell_count == 0:
        return 100
    
    ratio = buy_count / sell_count
    
    if ratio >= 10:
        return 90
    elif ratio >= 5:
        return 80
    elif ratio >= 2:
        return 60
    elif ratio >= 1:
        return 40
    else:
        return 20


def calculate_holding_milestones():
    """
    Calculate holding days and award milestone bonuses for all PRO token engagements
    Run this daily via background job
    """
    logger.info("🔄 Starting holding milestone calculation...")
    
    try:
        # Get all PRO tokens
        pro_tokens = [token for token in Token.query.all() if TokenService.is_pro_token(token)]
        
        logger.info(f"Found {len(pro_tokens)} PRO tokens")
        
        total_engagements = 0
        milestones_awarded = 0
        
        for token in pro_tokens:
            # Get all engagements for this token WHERE USER CURRENTLY HOLDS TOKENS
            # Join with blockchain data to ensure they actually hold tokens
            from services.holder_service import HolderService
            
            engagements = TokenEngagement.query.filter_by(token_id=token.id).all()
            
            for engagement in engagements:
                total_engagements += 1
                
                # Skip if user has never acquired tokens
                if not engagement.first_acquired_at:
                    continue
                
                # CRITICAL FIX: Only award holding milestones to current holders
                # Check if user currently holds tokens via blockchain
                try:
                    holding_info = HolderService.get_user_holding_info(
                        engagement.user.wallet_address,
                        token.contract_address
                    )
                    current_balance = float(holding_info.get('balance', 0))
                    
                    # Skip if user sold out (not a true diamond holder)
                    if current_balance == 0:
                        continue
                except Exception as e:
                    logger.warning(f"Could not check balance for {engagement.user.wallet_address}: {e}")
                    continue
                
                # Calculate holding days
                now = datetime.now(timezone.utc)
                holding_duration = now - engagement.first_acquired_at
                engagement.holding_days = holding_duration.days
                
                # Calculate diamond hands score
                engagement.diamond_hands_score = calculate_diamond_hands_score(
                    engagement.buy_count or 0,
                    engagement.sell_count or 0
                )
                
                # Award milestone bonuses (one-time only)
                points_awarded = 0
                
                if engagement.holding_days >= 365 and not engagement.milestone_365d_awarded:
                    points_awarded += 500
                    engagement.milestone_365d_awarded = True
                    logger.info(f"🏆 365-day milestone: {engagement.user.wallet_address[:10]}... in {token.symbol} (+500 pts)")
                
                if engagement.holding_days >= 180 and not engagement.milestone_180d_awarded:
                    points_awarded += 300
                    engagement.milestone_180d_awarded = True
                    logger.info(f"🏆 180-day milestone: {engagement.user.wallet_address[:10]}... in {token.symbol} (+300 pts)")
                
                if engagement.holding_days >= 90 and not engagement.milestone_90d_awarded:
                    points_awarded += 150
                    engagement.milestone_90d_awarded = True
                    logger.info(f"🏆 90-day milestone: {engagement.user.wallet_address[:10]}... in {token.symbol} (+150 pts)")
                
                if engagement.holding_days >= 60 and not engagement.milestone_60d_awarded:
                    points_awarded += 100
                    engagement.milestone_60d_awarded = True
                    logger.info(f"🏆 60-day milestone: {engagement.user.wallet_address[:10]}... in {token.symbol} (+100 pts)")
                
                if engagement.holding_days >= 30 and not engagement.milestone_30d_awarded:
                    points_awarded += 50
                    engagement.milestone_30d_awarded = True
                    logger.info(f"🏆 30-day milestone: {engagement.user.wallet_address[:10]}... in {token.symbol} (+50 pts)")
                
                if points_awarded > 0:
                    engagement.community_points = (engagement.community_points or 0) + points_awarded
                    engagement.last_activity_at = now
                    milestones_awarded += 1
        
        db.session.commit()
        
        logger.info(f"✅ Holding milestone calculation complete:")
        logger.info(f"   - Processed {total_engagements} engagements")
        logger.info(f"   - Awarded {milestones_awarded} milestone bonuses")
        
        return {
            'success': True,
            'engagements_processed': total_engagements,
            'milestones_awarded': milestones_awarded
        }
        
    except Exception as e:
        logger.error(f"❌ Error calculating holding milestones: {str(e)}", exc_info=True)
        db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    # Allow running directly for testing
    from main import app
    with app.app_context():
        result = calculate_holding_milestones()
        print(f"Result: {result}")
