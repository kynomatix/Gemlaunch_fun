"""
KAS/USD Price Oracle Service
Fetches Kaspa (KAS) price from CoinGecko API for USD valuation calculations
"""
import os
import requests
from datetime import datetime, timedelta

class KasPriceOracle:
    """Oracle service for fetching KAS/USD price"""
    
    def __init__(self):
        self.api_key = os.environ.get('COINGECKO_PRICE')
        self.cache = {}
        self.cache_duration = timedelta(minutes=5)
    
    def get_kas_price(self):
        """
        Fetch current KAS/USD price from CoinGecko
        Returns: float - Current KAS price in USD
        """
        # Check cache first
        if 'price' in self.cache and 'timestamp' in self.cache:
            if datetime.now() - self.cache['timestamp'] < self.cache_duration:
                return self.cache['price']
        
        try:
            # CoinGecko Free API endpoint
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "kaspa",
                "vs_currencies": "usd"
            }
            
            # Add API key header if available
            headers = {}
            if self.api_key:
                headers['x-cg-pro-api-key'] = self.api_key
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            price = data.get('kaspa', {}).get('usd', 0)
            
            # Update cache
            self.cache = {
                'price': price,
                'timestamp': datetime.now()
            }
            
            return price
            
        except Exception as e:
            print(f"Error fetching KAS price: {e}")
            # Return cached price if available, otherwise return 0
            return self.cache.get('price', 0)
    
    def calculate_graduation_threshold(self, target_usd=None):
        """
        Calculate KAS amount needed for target USD market cap
        Args:
            target_usd: Target market cap in USD (default: pulls from PlatformSettings)
        Returns: 
            int - KAS amount in wei (18 decimals)
        """
        if target_usd is None:
            from models import PlatformSettings
            target_usd = float(PlatformSettings.get_settings().graduation_threshold_usd)
        
        kas_price = self.get_kas_price()
        if kas_price <= 0:
            return 900000 * 10**18  # Fallback: 900K KAS
        
        kas_amount = target_usd / kas_price
        return int(kas_amount * 10**18)
    
    def get_market_cap_usd(self, kas_reserve_wei):
        """
        Calculate USD market cap for given KAS reserve
        Args:
            kas_reserve_wei: KAS amount in wei (18 decimals)
        Returns:
            float - Market cap in USD
        """
        kas_price = self.get_kas_price()
        kas_amount = kas_reserve_wei / 10**18
        return kas_amount * kas_price
    
    def get_oracle_status(self):
        """
        Get oracle status for admin dashboard
        Returns:
            dict - Oracle status information
        """
        kas_price = self.get_kas_price()
        is_cached = 'timestamp' in self.cache
        cache_age = None
        
        if is_cached:
            cache_age = (datetime.now() - self.cache['timestamp']).total_seconds()
        
        return {
            'kas_price': kas_price,
            'is_cached': is_cached,
            'cache_age_seconds': cache_age,
            'last_update': self.cache.get('timestamp'),
            'graduation_threshold_kas': self.calculate_graduation_threshold() / 10**18,
            'api_source': 'CoinGecko' + (' Pro' if self.api_key else ' Free')
        }

# Global oracle instance
oracle = KasPriceOracle()
