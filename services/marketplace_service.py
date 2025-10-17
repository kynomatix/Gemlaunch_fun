"""
Marketplace Service - Efficiently fetch real-time bonding curve data for token listings
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from flask import current_app
from models import Token

logger = logging.getLogger(__name__)


def parse_transfer_to_trade(transfer: Dict, token_address: str) -> Optional[Dict]:
    """
    Parse a GraphQL token transfer into a trade event.
    
    Filters out vesting contract transfers and other non-trade activity.
    Determines buy vs sell based on the direction (to/from bonding curve pool).
    
    Args:
        transfer: GraphQL transfer dict with buyer, seller, token_amount, timestamp, kas_value
        token_address: Token contract address (the bonding curve pool address)
        
    Returns:
        Dict with trade_type, timestamp, kas_amount, token_amount, trader_address
        Or None if not a valid trade (vesting, airdrop, etc.)
    """
    from datetime import datetime, timezone
    
    # Extract addresses
    from_addr = transfer.get('seller', '').lower()
    to_addr = transfer.get('buyer', '').lower()
    pool_addr = token_address.lower()
    
    # Skip if either address is missing
    if not from_addr or not to_addr:
        return None
    
    # Determine if this is a buy or sell
    # Buy: Pool (from) → User (to), User pays KAS
    # Sell: User (from) → Pool (to), User receives KAS
    
    if from_addr == pool_addr:
        # Buy: tokens going FROM pool TO user
        trade_type = 'buy'
        trader_address = to_addr
    elif to_addr == pool_addr:
        # Sell: tokens going FROM user TO pool
        trade_type = 'sell'
        trader_address = from_addr
    else:
        # Not a trade with the pool (could be vesting, airdrop, transfer, etc.)
        return None
    
    # Parse timestamp
    timestamp_str = transfer.get('timestamp', '')
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        timestamp = datetime.now(timezone.utc)
    
    # Extract amounts
    token_amount = float(transfer.get('token_amount', 0))
    kas_value = float(transfer.get('kas_value', 0)) / 1e18  # Convert from wei to KAS
    
    return {
        'trade_type': trade_type,
        'timestamp': timestamp,
        'kas_amount': kas_value,
        'token_amount': token_amount,
        'trader_address': trader_address,
        'tx_hash': transfer.get('tx_hash', '')
    }


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
    def get_24h_metrics(token_address: str) -> Dict:
        """
        Get 24h metrics (volume and price change) from GraphQL efficiently.
        
        Returns:
            dict: {
                'volume_24h': float,        # 24h volume in KAS
                'price_change_24h': float   # 24h price change percentage
            }
        """
        try:
            from services.blockscout_client import BlockscoutClient
            from services.web3_service import get_web3_service
            from datetime import timezone
            
            client = BlockscoutClient()
            web3_service = get_web3_service()
            
            # Get recent transfers (trades) from GraphQL
            transfers = client.get_token_transfers(token_address, first=8)
            
            if not transfers:
                return {'volume_24h': 0, 'price_change_24h': 0}
            
            # Calculate volume and price change from transfers within last 24 hours
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            total_volume = 0
            prices_24h_ago = []
            current_prices = []
            
            for transfer in transfers:
                # Parse timestamp
                timestamp = datetime.fromisoformat(transfer['timestamp'].replace('Z', '+00:00'))
                
                # Calculate trade price (KAS per token)
                kas_value = float(transfer.get('kas_value', 0)) / 1e18
                token_amount = float(transfer.get('token_amount', 0)) / 1e18
                
                if token_amount > 0:
                    price = kas_value / token_amount
                    
                    # Track recent prices for current price
                    current_prices.append(price)
                    
                    # Track older prices for 24h comparison
                    if timestamp < cutoff_time:
                        prices_24h_ago.append(price)
                
                # Add to volume if within 24h
                if timestamp >= cutoff_time:
                    total_volume += kas_value
            
            # Calculate price change
            price_change = 0
            if current_prices:
                current_price = current_prices[0]  # Most recent price
                
                if prices_24h_ago:
                    # Compare to 24h ago price
                    old_price = prices_24h_ago[-1]  # Oldest price beyond 24h
                    if old_price > 0:
                        price_change = ((current_price - old_price) / old_price) * 100
                elif len(current_prices) > 1:
                    # If no data beyond 24h, compare first to last trade
                    old_price = current_prices[-1]
                    if old_price > 0:
                        price_change = ((current_price - old_price) / old_price) * 100
            
            return {
                'volume_24h': round(total_volume, 2),
                'price_change_24h': round(price_change, 1)
            }
            
        except Exception as e:
            logger.debug(f"Could not fetch 24h metrics for {token_address}: {e}")
            return {'volume_24h': 0, 'price_change_24h': 0}
    
    @staticmethod
    def is_valid_address(address: str) -> bool:
        """Check if address is a valid hex address"""
        if not address or not isinstance(address, str):
            return False
        if not address.startswith('0x'):
            return False
        if len(address) != 42:  # 0x + 40 hex chars
            return False
        try:
            # Try to convert to checksum address to validate
            from web3 import Web3
            Web3.to_checksum_address(address)
            return True
        except:
            return False
    
    @staticmethod
    def enrich_tokens_with_marketplace_data(tokens: List[Token]) -> List[Token]:
        """
        Enrich token objects with real-time marketplace data.
        Only processes tokens with valid contract addresses.
        Optimized to enrich valid tokens first for better UX.
        
        Args:
            tokens: List of Token model instances
            
        Returns:
            List of Token instances with added attributes:
                - volume_24h: 24h trading volume in KAS
                - price_change_24h: 24h price change percentage
                - graduation_progress: Progress toward graduation
        """
        # Separate valid and invalid tokens
        valid_tokens = []
        invalid_tokens = []
        
        for token in tokens:
            if token.contract_address and MarketplaceService.is_valid_address(token.contract_address):
                valid_tokens.append(token)
            else:
                invalid_tokens.append(token)
        
        # Set defaults for all invalid tokens
        for token in invalid_tokens:
            token.volume_24h = 0
            token.price_change_24h = 0
            token.graduation_progress = 0
        
        # Enrich valid tokens (limit to prevent timeout)
        MAX_TOKENS_TO_ENRICH = 20  # Reduced for performance
        
        for i, token in enumerate(valid_tokens):
            # Set defaults first
            token.volume_24h = 0
            token.price_change_24h = 0
            token.graduation_progress = 0
            
            # Stop after limit
            if i >= MAX_TOKENS_TO_ENRICH:
                continue
            
            # Get 24h metrics (volume + price change) - cached for 10s
            try:
                metrics = MarketplaceService.get_24h_metrics(token.contract_address)
                token.volume_24h = metrics['volume_24h']
                token.price_change_24h = metrics['price_change_24h']
            except Exception as e:
                # Skip metrics on error
                pass
            
            # Get graduation progress from bonding curve (only if we got metrics successfully)
            if token.volume_24h > 0 or i < 10:  # Prioritize tokens with activity
                try:
                    from services.web3_service import get_web3_service
                    web3_service = get_web3_service()
                    pool_contract = web3_service.get_bonding_pool_contract(token.contract_address)
                    
                    if pool_contract:
                        virtual_kas_reserve = pool_contract.functions.virtualKasReserve().call()
                        initial_virtual_kas = pool_contract.functions.INITIAL_VIRTUAL_KAS().call()
                        kas_collected = virtual_kas_reserve - initial_virtual_kas
                        graduation_target = 5000 * 1e18
                        token.graduation_progress = min((kas_collected / graduation_target) * 100, 100) if graduation_target > 0 else 0
                except Exception as e:
                    # Skip graduation progress on error
                    pass
        
        logger.info(f"✅ Enriched {min(len(valid_tokens), MAX_TOKENS_TO_ENRICH)} of {len(valid_tokens)} valid tokens ({len(invalid_tokens)} invalid)")
        
        return tokens
