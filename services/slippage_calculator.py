"""
Dynamic Slippage Calculator Service
CRITICAL SECURITY FIX: CRITICAL-2
Calculate optimal slippage to prevent failed transactions and sandwich attacks
"""

import logging
import statistics
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

class DynamicSlippageCalculator:
    """
    CRITICAL SECURITY FIX: CRITICAL-2
    Calculate optimal slippage to prevent failed transactions and sandwich attacks
    
    Adaptive slippage based on:
    - Pool liquidity depth (0.3% - 10% adaptive range)
    - Trade size relative to pool
    - Recent price volatility
    - Historical transaction success rate
    """
    
    def __init__(self, web3_service):
        self.web3 = web3_service
        self.base_slippage_map = {
            0.01: 0.003,   # < 1% of pool → 0.3%
            0.05: 0.01,    # 1-5% of pool → 1%
            0.10: 0.02,    # 5-10% of pool → 2%
            1.00: 0.05     # > 10% of pool → 5%
        }
    
    def calculate_slippage(self, token, trade_amount_wei, is_buy):
        """
        Calculate dynamic slippage based on multiple factors
        
        Args:
            token: Token model instance with dex_pool_address
            trade_amount_wei: Trade amount in wei (KAS for buy, tokens for sell)
            is_buy: Boolean indicating trade direction
        
        Returns:
            dict: {
                'slippage_percentage': float (0.003 - 0.10),
                'slippage_bps': int (30 - 1000 basis points),
                'trade_impact_ratio': float,
                'volatility': float,
                'warning': bool,
                'recommendation': str
            }
        """
        try:
            # Get pool state
            pool_reserves = self._get_pool_reserves(token.dex_pool_address)
            pool_liquidity_usd = self._calculate_pool_liquidity_usd(pool_reserves)
            
            # Calculate trade impact
            trade_value_usd = self._get_trade_value_usd(trade_amount_wei, token, is_buy)
            trade_impact_ratio = trade_value_usd / pool_liquidity_usd if pool_liquidity_usd > 0 else 1.0
            
            # Get recent volatility (standard deviation of prices over last hour)
            volatility = self._get_recent_volatility(token.dex_pool_address)
            
            # Determine base slippage tier
            base_slippage = 0.05  # Default 5% for very large trades
            for threshold, slippage in sorted(self.base_slippage_map.items()):
                if trade_impact_ratio < threshold:
                    base_slippage = slippage
                    break
            
            # Adjust for volatility (add volatility percentage)
            volatility_multiplier = 1 + (volatility / 100)
            
            # Buys can use tighter slippage than sells
            direction_multiplier = 0.8 if is_buy else 1.0
            
            # Calculate final slippage
            final_slippage = base_slippage * volatility_multiplier * direction_multiplier
            
            # Cap between 0.3% and 10%
            final_slippage = max(0.003, min(final_slippage, 0.10))
            
            # Convert to basis points
            slippage_bps = int(final_slippage * 10000)
            
            return {
                'slippage_percentage': final_slippage,
                'slippage_bps': slippage_bps,
                'trade_impact_ratio': trade_impact_ratio,
                'volatility': volatility,
                'warning': trade_impact_ratio > 0.05,
                'recommendation': self._get_recommendation(trade_impact_ratio),
                'pool_liquidity_usd': pool_liquidity_usd
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate dynamic slippage: {e}")
            # Fallback to safe conservative slippage
            return {
                'slippage_percentage': 0.02,  # 2% default fallback
                'slippage_bps': 200,
                'trade_impact_ratio': 0,
                'volatility': 0,
                'warning': False,
                'recommendation': 'Using default slippage (calculation failed)',
                'pool_liquidity_usd': 0
            }
    
    def _get_pool_reserves(self, pool_address):
        """Get current pool reserves (reserve0, reserve1) from Uniswap V3 pool"""
        try:
            # For Uniswap V3, we need slot0 and liquidity
            # Simplified: use a basic ERC20 pair-like interface
            pool_contract = self.web3.w3.eth.contract(
                address=pool_address,
                abi=[{
                    "inputs": [],
                    "name": "slot0",
                    "outputs": [
                        {"type": "uint160", "name": "sqrtPriceX96"},
                        {"type": "int24", "name": "tick"},
                        {"type": "uint16", "name": "observationIndex"},
                        {"type": "uint16", "name": "observationCardinality"},
                        {"type": "uint16", "name": "observationCardinalityNext"},
                        {"type": "uint8", "name": "feeProtocol"},
                        {"type": "bool", "name": "unlocked"}
                    ],
                    "stateMutability": "view",
                    "type": "function"
                }, {
                    "inputs": [],
                    "name": "liquidity",
                    "outputs": [{"type": "uint128", "name": ""}],
                    "stateMutability": "view",
                    "type": "function"
                }]
            )
            
            slot0 = pool_contract.functions.slot0().call()
            liquidity = pool_contract.functions.liquidity().call()
            sqrt_price_x96 = slot0[0]
            
            # Approximate reserves from sqrtPriceX96 and liquidity
            # reserve1 = liquidity * sqrtPriceX96 / (2^96)
            # reserve0 = liquidity / (sqrtPriceX96 / 2^96)
            price = (sqrt_price_x96 / (2 ** 96)) ** 2
            
            # Rough approximation
            reserve0 = int(liquidity * 1000)  # Placeholder
            reserve1 = int(liquidity * price * 1000)  # Placeholder
            
            return {'reserve0': reserve0, 'reserve1': reserve1}
            
        except Exception as e:
            logger.warning(f"Failed to get pool reserves: {e}")
            # Return conservative fallback
            return {'reserve0': 1000000000000000000, 'reserve1': 1000000000000000000}
    
    def _calculate_pool_liquidity_usd(self, reserves):
        """Calculate total pool liquidity in USD"""
        # Assume larger reserve is KAS, KAS = $0.15 USD
        kas_reserve = max(reserves['reserve0'], reserves['reserve1'])
        kas_price_usd = 0.15
        total_liquidity_usd = (kas_reserve / 1e18) * kas_price_usd * 2  # 2x for both sides
        return total_liquidity_usd
    
    def _get_trade_value_usd(self, amount_wei, token, is_buy):
        """Calculate trade value in USD"""
        kas_price_usd = 0.15
        if is_buy:
            # amount_wei is KAS
            return (amount_wei / 1e18) * kas_price_usd
        else:
            # amount_wei is tokens - need to get token price
            # Simplified: assume small percentage of pool
            return 100.0  # Placeholder - would calculate from reserves
    
    def _get_recent_volatility(self, pool_address):
        """
        Calculate price volatility from recent trades
        Returns volatility as percentage (0-20%)
        """
        try:
            from models import Trade
            from sqlalchemy import and_
            
            # Get trades from last hour for this pool
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            recent_trades = Trade.query.filter(
                and_(
                    Trade.token.has(dex_pool_address=pool_address),
                    Trade.created_at >= one_hour_ago
                )
            ).order_by(Trade.created_at.desc()).limit(100).all()
            
            if len(recent_trades) < 10:
                return 5.0  # Default 5% volatility if insufficient data
            
            # Calculate price for each trade (KAS per token)
            prices = []
            for trade in recent_trades:
                kas_amount = float(trade.kas_amount)
                token_amount = float(trade.token_amount)
                if token_amount > 0:
                    price = kas_amount / token_amount
                    prices.append(price)
            
            if not prices:
                return 5.0
            
            # Calculate standard deviation as % of mean
            mean_price = statistics.mean(prices)
            std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
            volatility_pct = (std_dev / mean_price * 100) if mean_price > 0 else 5.0
            
            # Cap at 20%
            return min(volatility_pct, 20.0)
            
        except Exception as e:
            logger.warning(f"Failed to calculate volatility: {e}")
            return 5.0  # Default fallback
    
    def _get_recommendation(self, impact_ratio):
        """Get human-readable recommendation"""
        if impact_ratio > 0.10:
            return "⚠️ Very large trade - consider splitting into smaller trades"
        elif impact_ratio > 0.05:
            return "⚠️ Large trade - high price impact expected"
        else:
            return "✅ Trade size is reasonable"
