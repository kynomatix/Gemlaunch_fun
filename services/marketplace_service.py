"""
Marketplace Service - Efficiently fetch real-time bonding curve data for token listings
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from flask import current_app
from models import Token

logger = logging.getLogger(__name__)


class MarketplaceService:
    """Service for fetching marketplace token data with bonding curve metrics"""
    
    @staticmethod
    def get_bonding_curve_progress(token_address: str) -> Dict:
        """
        Get bonding curve fill percentage for a token.
        
        Returns:
            dict: {
                'fill_percentage': float,  # How full the bonding curve is (0-100)
                'tokens_sold': float,      # Tokens sold from bonding curve
                'graduation_progress': float  # Progress toward graduation (0-100)
            }
        """
        try:
            from services.web3_service import get_web3_service
            web3_service = get_web3_service()
            
            # Load bonding curve pool contract
            pool_contract = web3_service.get_bonding_pool_contract(token_address)
            
            if not pool_contract:
                return {
                    'fill_percentage': 0,
                    'tokens_sold': 0,
                    'graduation_progress': 0
                }
            
            # Get virtual reserves (state variables that update on each trade)
            virtual_token_reserve = pool_contract.functions.virtualTokenReserve().call()
            virtual_kas_reserve = pool_contract.functions.virtualKasReserve().call()
            initial_virtual_kas = pool_contract.functions.INITIAL_VIRTUAL_KAS().call()
            
            # Get curve supply percentage (how much of total supply is on the curve)
            curve_supply_pct = pool_contract.functions.CURVE_SUPPLY_PCT().call()  # In basis points (10000 = 100%)
            total_supply = pool_contract.functions.totalSupply().call()
            
            # Calculate initial virtual token reserve
            initial_virtual_token_reserve = (total_supply * curve_supply_pct) // 10000
            
            # Tokens sold = how much virtual token reserve has decreased
            tokens_sold = initial_virtual_token_reserve - virtual_token_reserve
            
            # Calculate fill percentage (how much of the bonding curve has been bought)
            fill_percentage = (tokens_sold / initial_virtual_token_reserve) * 100 if initial_virtual_token_reserve > 0 else 0
            
            # Graduation progress based on KAS collected (more KAS = closer to graduation)
            # The more KAS collected, the closer to graduation
            kas_collected = virtual_kas_reserve - initial_virtual_kas
            # Use a target of ~5000 KAS for graduation as a rough estimate
            graduation_target = 5000 * 1e18  # 5000 KAS in wei
            graduation_progress = min((kas_collected / graduation_target) * 100, 100) if graduation_target > 0 else 0
            
            return {
                'fill_percentage': round(fill_percentage, 2),
                'tokens_sold': tokens_sold / 1e18,  # Convert from wei
                'graduation_progress': round(graduation_progress, 2)
            }
            
        except Exception as e:
            logger.debug(f"Could not fetch bonding curve progress for {token_address}: {e}")
            return {
                'fill_percentage': 0,
                'tokens_sold': 0,
                'graduation_progress': 0
            }
    
    @staticmethod
    def get_24h_trade_volume(token_address: str) -> float:
        """
        Get 24h trading volume from GraphQL.
        
        Returns:
            float: 24h volume in KAS
        """
        try:
            from services.blockscout_client import BlockscoutClient
            from datetime import timezone
            client = BlockscoutClient()
            
            # Get recent transfers (trades) from GraphQL
            transfers = client.get_token_transfers(token_address, first=8)
            
            # Calculate volume from transfers within last 24 hours
            # Use timezone-aware datetime for comparison
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            total_volume = 0
            for transfer in transfers:
                # Parse timestamp and check if within 24h window
                timestamp = datetime.fromisoformat(transfer['timestamp'].replace('Z', '+00:00'))
                if timestamp >= cutoff_time:
                    kas_amount = float(transfer.get('kas_value', 0)) / 1e18  # Convert from wei
                    total_volume += kas_amount
            
            return round(total_volume, 2)
            
        except Exception as e:
            logger.debug(f"Could not fetch 24h volume for {token_address}: {e}")
            return 0
    
    @staticmethod
    def enrich_tokens_with_marketplace_data(tokens: List[Token]) -> List[Token]:
        """
        Enrich token objects with real-time marketplace data.
        
        Args:
            tokens: List of Token model instances
            
        Returns:
            List of Token instances with added attributes:
                - bonding_curve_fill: Percentage of bonding curve filled
                - volume_24h: 24h trading volume in KAS
                - graduation_progress: Progress toward graduation
        """
        for token in tokens:
            if not token.contract_address:
                # Token not deployed yet
                token.bonding_curve_fill = 0
                token.volume_24h = 0
                token.graduation_progress = 0
                continue
            
            # Get bonding curve data
            curve_data = MarketplaceService.get_bonding_curve_progress(token.contract_address)
            token.bonding_curve_fill = curve_data['fill_percentage']
            token.graduation_progress = curve_data['graduation_progress']
            
            # Get 24h volume
            token.volume_24h = MarketplaceService.get_24h_trade_volume(token.contract_address)
        
        return tokens
