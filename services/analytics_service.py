"""
Analytics Service for Gemlaunch Platform
Provides reusable analytics calculation functions
"""
import logging
from sqlalchemy import func, distinct
from models import db, Token, TradeEvent
from services.kas_oracle import oracle

def calculate_tvl():
    """Calculate Total Value Locked in KAS
    
    TVL includes ONLY pre-graduation bonding curve tokens.
    Graduated tokens are on DEX and not part of platform TVL.
    
    Returns:
        dict: {'tvl_kas': float, 'tvl_usd': float}
    """
    try:
        # Sum kas_reserve for ONLY pre-graduation tokens
        tvl_result = db.session.query(
            func.sum(Token.kas_reserve)
        ).filter(
            Token.graduation_status != 'graduated',
            Token.deployment_status == 'deployed'
        ).scalar()
        
        tvl_kas = float(tvl_result) if tvl_result else 0.0
        
        # Convert to USD
        kas_price = oracle.get_kas_price()
        tvl_usd = tvl_kas * kas_price
        
        return {
            'tvl_kas': tvl_kas,
            'tvl_usd': tvl_usd
        }
    except Exception as e:
        logging.error(f"Error calculating TVL: {e}")
        return {'tvl_kas': 0.0, 'tvl_usd': 0.0}

def calculate_volume():
    """Calculate total trading volume in KAS
    
    Sums kas_amount from all TradeEvents. Each trade event records the KAS amount
    involved in the trade (not doubled for buy/sell pairs).
    
    Returns:
        dict: {'total_volume_kas': float, 'total_volume_usd': float}
    """
    try:
        # Sum kas_amount from all trades (not doubled)
        # TradeEvent stores kas_amount as the KAS involved (positive for both buy/sell)
        volume_result = db.session.query(
            func.sum(TradeEvent.kas_amount)
        ).scalar()
        
        total_volume_kas = float(volume_result) if volume_result else 0.0
        
        # Convert to USD
        kas_price = oracle.get_kas_price()
        total_volume_usd = total_volume_kas * kas_price
        
        return {
            'total_volume_kas': total_volume_kas,
            'total_volume_usd': total_volume_usd
        }
    except Exception as e:
        logging.error(f"Error calculating volume: {e}")
        return {'total_volume_kas': 0.0, 'total_volume_usd': 0.0}

def calculate_token_stats():
    """Calculate token statistics
    
    Returns:
        dict: Token counts and stats
    """
    try:
        # Total tokens
        total_tokens = db.session.query(func.count(Token.id)).scalar() or 0
        
        # Average market cap for active (non-graduated) tokens
        avg_mc_result = db.session.query(
            func.avg(Token.current_market_cap)
        ).filter(
            Token.graduation_status != 'graduated',
            Token.deployment_status == 'deployed'
        ).scalar()
        
        avg_market_cap_kas = float(avg_mc_result) if avg_mc_result else 0.0
        
        # Convert to USD
        kas_price = oracle.get_kas_price()
        avg_market_cap_usd = avg_market_cap_kas * kas_price
        
        return {
            'total_tokens': total_tokens,
            'average_market_cap_kas': avg_market_cap_kas,
            'average_market_cap_usd': avg_market_cap_usd
        }
    except Exception as e:
        logging.error(f"Error calculating token stats: {e}")
        return {
            'total_tokens': 0,
            'average_market_cap_kas': 0.0,
            'average_market_cap_usd': 0.0
        }

def calculate_trade_stats():
    """Calculate trade statistics
    
    Returns:
        dict: Trade counts and unique traders
    """
    try:
        # Total trades
        total_trades = db.session.query(func.count(TradeEvent.id)).scalar() or 0
        
        # Unique traders - count distinct user_ids
        unique_traders = db.session.query(
            func.count(distinct(TradeEvent.user_id))
        ).scalar() or 0
        
        return {
            'total_trades': total_trades,
            'unique_traders': unique_traders
        }
    except Exception as e:
        logging.error(f"Error calculating trade stats: {e}")
        return {
            'total_trades': 0,
            'unique_traders': 0
        }

def get_top_tokens_by_volume(limit=10):
    """Get top tokens by 24h trading volume
    
    Args:
        limit: Number of tokens to return (default 10)
        
    Returns:
        list: List of token data dicts
    """
    try:
        top_tokens = db.session.query(Token).filter(
            Token.deployment_status == 'deployed'
        ).order_by(
            Token.trading_volume_24h.desc()
        ).limit(limit).all()
        
        kas_price = oracle.get_kas_price()
        
        tokens_data = []
        for token in top_tokens:
            volume_24h_kas = float(token.trading_volume_24h) if token.trading_volume_24h else 0.0
            market_cap_kas = float(token.current_market_cap) if token.current_market_cap else 0.0
            price_kas = float(token.current_price) if token.current_price else 0.0
            
            tokens_data.append({
                'token_id': token.id,
                'name': token.name,
                'symbol': token.symbol,
                'contract_address': token.contract_address,
                'image_url': token.image_url,
                'volume_24h_kas': volume_24h_kas,
                'volume_24h_usd': volume_24h_kas * kas_price,
                'market_cap_kas': market_cap_kas,
                'market_cap_usd': market_cap_kas * kas_price,
                'price_kas': price_kas,
                'graduation_status': token.graduation_status
            })
        
        return tokens_data
    except Exception as e:
        logging.error(f"Error getting top tokens: {e}")
        return []

def get_platform_analytics():
    """Get comprehensive platform analytics
    
    This is a convenience function that combines all analytics calculations.
    Used by both the analytics dashboard and GraphQL API.
    
    Returns:
        dict: Complete analytics data
    """
    try:
        # Get KAS price once
        kas_price = oracle.get_kas_price()
        
        # Calculate all metrics
        tvl_data = calculate_tvl()
        volume_data = calculate_volume()
        token_stats = calculate_token_stats()
        trade_stats = calculate_trade_stats()
        top_tokens = get_top_tokens_by_volume(10)
        
        return {
            'tvl_kas': tvl_data['tvl_kas'],
            'tvl_usd': tvl_data['tvl_usd'],
            'total_volume_kas': volume_data['total_volume_kas'],
            'total_volume_usd': volume_data['total_volume_usd'],
            'total_tokens': token_stats['total_tokens'],
            'average_market_cap_kas': token_stats['average_market_cap_kas'],
            'average_market_cap_usd': token_stats['average_market_cap_usd'],
            'total_trades': trade_stats['total_trades'],
            'unique_traders': trade_stats['unique_traders'],
            'kas_price_usd': kas_price,
            'top_tokens_by_volume': top_tokens
        }
    except Exception as e:
        logging.error(f"Error fetching platform analytics: {e}")
        # Return safe defaults on error
        return {
            'tvl_kas': 0.0,
            'tvl_usd': 0.0,
            'total_volume_kas': 0.0,
            'total_volume_usd': 0.0,
            'total_tokens': 0,
            'average_market_cap_kas': 0.0,
            'average_market_cap_usd': 0.0,
            'total_trades': 0,
            'unique_traders': 0,
            'kas_price_usd': 0.0,
            'top_tokens_by_volume': []
        }
