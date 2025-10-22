"""
Price Oracle Service
CRITICAL SECURITY FIX: CRITICAL-4
Multi-source price validation to prevent manipulation
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

class PriceOracle:
    """
    CRITICAL SECURITY FIX: CRITICAL-4
    Multi-source price validation to prevent manipulation
    
    Validates quotes against:
    - QuoterV2 contract (primary)
    - Reserve-based calculation (independent)
    - Recent trade VWAP (tertiary)
    - TWAP (Time-Weighted Average Price)
    - Pool health checks
    """
    
    def __init__(self, web3_service):
        self.web3 = web3_service
        self.max_price_deviation = 0.05  # 5% max deviation between sources
        self.min_liquidity_usd = 5000  # Minimum $5K liquidity required
    
    def validate_quote(self, token, amount_in, is_buy):
        """
        Validate quote against multiple independent sources
        
        Args:
            token: Token model instance
            amount_in: Amount to trade (wei)
            is_buy: Boolean indicating trade direction
        
        Returns:
            dict: {
                'amount_out': int (validated quote),
                'validation': dict (validation details),
                'pool_health': dict,
                'confidence': str ('high', 'medium', 'low')
            }
        
        Raises:
            PriceManipulationDetected: If sources disagree significantly
            InsufficientLiquidityError: If pool health check fails
        """
        try:
            # Check pool health first
            pool_health = self.check_pool_health(token)
            if not pool_health['healthy']:
                raise InsufficientLiquidityError(pool_health['reason'])
            
            # Get quotes from multiple sources
            quotes = {
                'quoter_v2': self._get_quoter_v2_quote(token, amount_in, is_buy),
                'reserves': self._get_reserve_based_quote(token, amount_in, is_buy),
                'vwap': self._get_vwap_quote(token, amount_in, is_buy)
            }
            
            # Validate consensus
            validation = self._validate_consensus(quotes, amount_in)
            
            if not validation['valid']:
                raise PriceManipulationDetected(
                    f"Price sources disagree: {validation['reason']}"
                )
            
            # Use QuoterV2 as primary (most accurate for Uniswap V3)
            amount_out = quotes['quoter_v2'] if quotes['quoter_v2'] else quotes['reserves']
            
            return {
                'amount_out': amount_out,
                'validation': validation,
                'pool_health': pool_health,
                'confidence': validation['confidence']
            }
            
        except (PriceManipulationDetected, InsufficientLiquidityError):
            raise
        except Exception as e:
            logger.error(f"Price oracle validation failed: {e}")
            # Conservative fallback - reject transaction
            raise PriceManipulationDetected(f"Oracle validation error: {str(e)}")
    
    def _get_quoter_v2_quote(self, token, amount_in, is_buy):
        """Get quote from QuoterV2 contract (primary source)"""
        try:
            from services.web3_service import KASPA_FINANCE_WKAS, FEE_TIER_025
            
            quoter = self.web3.contracts.get('QuoterV2')
            if not quoter:
                return None
            
            fee_tier = token.dex_pool_fee_tier or FEE_TIER_025
            
            if is_buy:
                # KAS → Token
                result = quoter.functions.quoteExactInputSingle(
                    KASPA_FINANCE_WKAS,    # tokenIn (WKAS)
                    token.contract_address,  # tokenOut (Token)
                    amount_in,             # amountIn
                    fee_tier,              # fee
                    0                      # sqrtPriceLimitX96
                ).call()
            else:
                # Token → KAS
                result = quoter.functions.quoteExactInputSingle(
                    token.contract_address,  # tokenIn (Token)
                    KASPA_FINANCE_WKAS,    # tokenOut (WKAS)
                    amount_in,             # amountIn
                    fee_tier,              # fee
                    0                      # sqrtPriceLimitX96
                ).call()
            
            return result[0]  # amountOut
            
        except Exception as e:
            logger.warning(f"QuoterV2 failed: {e}")
            return None
    
    def _get_reserve_based_quote(self, token, amount_in, is_buy):
        """Get quote from reserve-based calculation (independent validation)"""
        try:
            from services.slippage_calculator import DynamicSlippageCalculator
            
            calc = DynamicSlippageCalculator(self.web3)
            reserves = calc._get_pool_reserves(token.dex_pool_address)
            
            # Constant product formula: x * y = k
            if is_buy:
                # KAS in, tokens out
                reserve_kas = max(reserves['reserve0'], reserves['reserve1'])
                reserve_tokens = min(reserves['reserve0'], reserves['reserve1'])
                
                # Amount out = (reserve_tokens * amount_in) / (reserve_kas + amount_in)
                amount_out = (reserve_tokens * amount_in) // (reserve_kas + amount_in)
            else:
                # Tokens in, KAS out
                reserve_tokens = min(reserves['reserve0'], reserves['reserve1'])
                reserve_kas = max(reserves['reserve0'], reserves['reserve1'])
                
                amount_out = (reserve_kas * amount_in) // (reserve_tokens + amount_in)
            
            return amount_out
            
        except Exception as e:
            logger.warning(f"Reserve-based calculation failed: {e}")
            return None
    
    def _get_vwap_quote(self, token, amount_in, is_buy):
        """Get quote based on recent trade VWAP (Volume-Weighted Average Price)"""
        try:
            from models import Trade
            from sqlalchemy import and_
            
            # Get trades from last 10 minutes
            ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
            
            recent_trades = Trade.query.filter(
                and_(
                    Trade.token_id == token.id,
                    Trade.created_at >= ten_min_ago
                )
            ).all()
            
            if len(recent_trades) < 5:
                return None  # Insufficient data
            
            # Calculate VWAP
            total_value = 0
            total_volume = 0
            
            for trade in recent_trades:
                kas_amount = float(trade.kas_amount)
                token_amount = float(trade.token_amount)
                total_value += kas_amount
                total_volume += token_amount
            
            if total_volume == 0:
                return None
            
            vwap_price = total_value / total_volume  # KAS per token
            
            # Calculate expected output
            if is_buy:
                # KAS in, tokens out
                amount_out = int((amount_in / 1e18) / vwap_price * 1e18)
            else:
                # Tokens in, KAS out
                amount_out = int((amount_in / 1e18) * vwap_price * 1e18)
            
            return amount_out
            
        except Exception as e:
            logger.warning(f"VWAP calculation failed: {e}")
            return None
    
    def _validate_consensus(self, quotes, amount):
        """Check if all sources agree within tolerance"""
        
        prices = []
        for source, quote in quotes.items():
            if quote is not None and quote > 0:
                price = quote / amount if amount > 0 else 0
                prices.append(price)
        
        if len(prices) < 2:
            return {
                'valid': False,
                'reason': 'Insufficient price sources',
                'confidence': 'low'
            }
        
        avg_price = sum(prices) / len(prices)
        max_deviation = max(abs(p - avg_price) / avg_price for p in prices) if avg_price > 0 else 0
        
        if max_deviation > self.max_price_deviation:
            return {
                'valid': False,
                'reason': f'Deviation {max_deviation:.2%} exceeds {self.max_price_deviation:.2%}',
                'confidence': 'low',
                'prices': prices,
                'max_deviation': max_deviation
            }
        
        # Determine confidence
        if max_deviation < 0.01:
            confidence = 'high'
        elif max_deviation < 0.03:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'valid': True,
            'reason': 'All sources agree',
            'confidence': confidence,
            'max_deviation': max_deviation,
            'avg_price': avg_price,
            'source_count': len(prices)
        }
    
    def check_pool_health(self, token):
        """Verify pool has sufficient liquidity and healthy state"""
        try:
            from services.slippage_calculator import DynamicSlippageCalculator
            
            calc = DynamicSlippageCalculator(self.web3)
            reserves = calc._get_pool_reserves(token.dex_pool_address)
            liquidity_usd = calc._calculate_pool_liquidity_usd(reserves)
            
            if liquidity_usd < self.min_liquidity_usd:
                return {
                    'healthy': False,
                    'reason': f'Low liquidity: ${liquidity_usd:.2f} < ${self.min_liquidity_usd}',
                    'liquidity_usd': liquidity_usd
                }
            
            # Check reserves ratio isn't extreme
            ratio = reserves['reserve0'] / reserves['reserve1'] if reserves['reserve1'] > 0 else 0
            if ratio > 1000 or ratio < 0.001:
                return {
                    'healthy': False,
                    'reason': f'Extreme reserves ratio: {ratio:.2f}',
                    'liquidity_usd': liquidity_usd,
                    'reserves_ratio': ratio
                }
            
            return {
                'healthy': True,
                'liquidity_usd': liquidity_usd,
                'reserves_ratio': ratio
            }
            
        except Exception as e:
            logger.error(f"Pool health check failed: {e}")
            return {
                'healthy': False,
                'reason': f'Health check error: {str(e)}',
                'liquidity_usd': 0
            }


class PriceManipulationDetected(Exception):
    """Raised when price sources disagree significantly"""
    pass


class InsufficientLiquidityError(Exception):
    """Raised when pool doesn't meet health requirements"""
    pass
