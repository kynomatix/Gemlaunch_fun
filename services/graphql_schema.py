"""
GraphQL Schema for Gemlaunch Analytics API
Provides comprehensive analytics data for the platform
"""
import graphene
from graphene import ObjectType, String, Float, Int, List, Field
from services.analytics_service import get_platform_analytics

class TokenVolumeType(graphene.ObjectType):
    """Top token by volume"""
    token_id = Int()
    name = String()
    symbol = String()
    contract_address = String()
    image_url = String()
    volume_24h_kas = Float()
    volume_24h_usd = Float()
    market_cap_kas = Float()
    market_cap_usd = Float()
    price_kas = Float()
    graduation_status = String()

class PlatformAnalyticsType(graphene.ObjectType):
    """Platform-wide analytics metrics"""
    tvl_kas = Float(description="Total Value Locked in KAS (pre-graduation tokens only)")
    tvl_usd = Float(description="Total Value Locked in USD")
    total_volume_kas = Float(description="Total trading volume in KAS")
    total_volume_usd = Float(description="Total trading volume in USD")
    total_tokens = Int(description="Total number of tokens")
    total_trades = Int(description="Total number of trades")
    unique_traders = Int(description="Number of unique traders")
    average_market_cap_kas = Float(description="Average market cap for active tokens (KAS)")
    average_market_cap_usd = Float(description="Average market cap for active tokens (USD)")
    kas_price_usd = Float(description="Current KAS price in USD")
    top_tokens_by_volume = List(TokenVolumeType, description="Top 10 tokens by 24h volume")

class Query(graphene.ObjectType):
    """Root query for analytics"""
    platform_analytics = Field(PlatformAnalyticsType, description="Get platform-wide analytics")
    
    def resolve_platform_analytics(self, info):
        """Resolve platform analytics query using shared analytics service"""
        analytics = get_platform_analytics()
        
        # Convert top tokens list to TokenVolumeType objects
        top_tokens_data = [
            TokenVolumeType(**token) for token in analytics['top_tokens_by_volume']
        ]
        
        return PlatformAnalyticsType(
            tvl_kas=analytics['tvl_kas'],
            tvl_usd=analytics['tvl_usd'],
            total_volume_kas=analytics['total_volume_kas'],
            total_volume_usd=analytics['total_volume_usd'],
            total_tokens=analytics['total_tokens'],
            total_trades=analytics['total_trades'],
            unique_traders=analytics['unique_traders'],
            average_market_cap_kas=analytics['average_market_cap_kas'],
            average_market_cap_usd=analytics['average_market_cap_usd'],
            kas_price_usd=analytics['kas_price_usd'],
            top_tokens_by_volume=top_tokens_data
        )

schema = graphene.Schema(query=Query)
