import os
import secrets
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(db.Model):
    """User model for wallet-based authentication"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Wallet is the primary identifier (no email/password)
    wallet_address = db.Column(db.String(128), unique=True, nullable=False, index=True)
    
    # Optional display name
    display_name = db.Column(db.String(64), nullable=True)
    
    # Profile information
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    
    # Wallet type (kastle, metamask, etc.)
    wallet_type = db.Column(db.String(32), nullable=True)
    
    # GEM points and gamification
    gem_points = db.Column(db.Integer, default=0)
    total_tokens_created = db.Column(db.Integer, default=0)
    total_trading_volume = db.Column(db.Numeric(precision=20, scale=8), default=0)
    
    # Cached tracking fields for achievement progress
    total_graduated_tokens = db.Column(db.Integer, default=0)
    total_trades_count = db.Column(db.Integer, default=0)
    total_messages_sent = db.Column(db.Integer, default=0)
    longest_holding_days = db.Column(db.Integer, default=0)
    
    # Account merge tracking
    archived = db.Column(db.Boolean, default=False)
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    tokens_created = db.relationship('Token', backref='creator', lazy='dynamic')
    trades = db.relationship('Trade', backref='user', lazy='dynamic')
    linked_wallets = db.relationship('LinkedWallet', backref='owner', lazy='dynamic')
    
    def add_gem_points(self, points):
        """Add GEM points to user"""
        self.gem_points = (self.gem_points or 0) + points
        db.session.commit()
    
    @staticmethod
    def resolve_wallet_to_user(wallet_address):
        """Resolve a wallet address to a User account
        
        Resolution order:
        1. Check LinkedWallet table first (for merged accounts)
        2. Check User.wallet_address (primary wallet)
        3. Return None if not found
        
        Args:
            wallet_address: Wallet address to resolve (will be lowercased)
            
        Returns:
            User object or None
        """
        from models import LinkedWallet
        
        wallet_lower = wallet_address.lower()
        
        # First, check if this wallet is linked to another account
        linked_wallet = LinkedWallet.query.filter_by(
            wallet_address=wallet_lower,
            status='verified'
        ).first()
        
        if linked_wallet:
            return User.query.get(linked_wallet.user_id)
        
        # If not linked, check if it's a primary wallet
        return User.query.filter_by(wallet_address=wallet_lower).first()
    
    @classmethod
    def get_or_create_by_wallet(cls, wallet_address, wallet_type=None, display_name=None):
        """Get existing user or create new one by wallet address
        
        Resolution order:
        1. Check if wallet is a linked wallet (LinkedWallet table) - FIRST to handle merged accounts
        2. Check if wallet is a primary wallet (User.wallet_address)
        3. Create new user if not found
        """
        wallet_lower = wallet_address.lower()
        
        # Use shared resolution utility
        user = cls.resolve_wallet_to_user(wallet_address)
        
        if not user:
            # Wallet not found anywhere - create new user
            user = cls(
                wallet_address=wallet_lower,
                wallet_type=wallet_type,
                display_name=display_name or f"User-{wallet_address[:8]}"
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update last seen for existing user
            user.last_seen = datetime.now(timezone.utc)
            if wallet_type:
                user.wallet_type = wallet_type
            db.session.commit()
        
        return user
    
    def __repr__(self):
        return f'<User {self.wallet_address[:10]}...>'

class Token(db.Model):
    """Token model for created memecoins"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic token info
    name = db.Column(db.String(128), nullable=False)
    symbol = db.Column(db.String(16), nullable=False, index=True)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(512))
    
    # Social links (based on Pump.sol contract)
    website = db.Column(db.String(512))
    twitter = db.Column(db.String(512))
    telegram = db.Column(db.String(512))
    
    # Token configuration
    total_supply = db.Column(db.Numeric(precision=30, scale=0), default=1000000000)  # 1B default
    reserved_tokens = db.Column(db.Numeric(precision=30, scale=0), default=0)
    reserved_percentage = db.Column(db.Float, default=0.0)  # 0-25%
    anti_bot_enabled = db.Column(db.Boolean, default=False)  # Anti-bot protection (GEM system)
    
    # Reserve allocation breakdown (% of reserve, must total 100)
    airdrops_allocation = db.Column(db.Float, default=33.0)  # % of reserve for airdrops
    marketing_allocation = db.Column(db.Float, default=33.0)  # % of reserve for marketing
    team_allocation = db.Column(db.Float, default=34.0)  # % of reserve for team
    total_airdropped = db.Column(db.Numeric(precision=30, scale=0), default=0)  # Total tokens airdropped so far
    
    # Blockchain info
    contract_address = db.Column(db.String(128), unique=True, nullable=True, index=True)
    deployment_tx = db.Column(db.String(128))
    deployment_status = db.Column(db.String(32), default='pending')  # pending, deploying, deployed, failed
    
    # PRO Token Vesting Contract Addresses (null for BASIC tokens)
    marketing_vesting_address = db.Column(db.String(128), nullable=True)
    team_vesting_address = db.Column(db.String(128), nullable=True)
    airdrop_vesting_address = db.Column(db.String(128), nullable=True)
    vesting_deployment_tx = db.Column(db.String(128), nullable=True)  # Vesting deployment tx hash (for monitoring)
    vesting_deployment_status = db.Column(db.String(32), default='none')  # none, pending, deployed, failed
    
    # Market data
    current_market_cap = db.Column(db.Numeric(precision=20, scale=8), default=1000)  # Start at ~$1K
    current_price = db.Column(db.Numeric(precision=20, scale=12), default=0.000001)
    circulating_supply = db.Column(db.Numeric(precision=30, scale=0), default=0)
    trading_volume_24h = db.Column(db.Numeric(precision=20, scale=8), default=0)
    
    # Bonding curve state
    kas_reserve = db.Column(db.Numeric(precision=20, scale=8), default=0)
    token_reserve = db.Column(db.Numeric(precision=30, scale=0))
    is_graduated = db.Column(db.Boolean, default=False)
    graduation_tx = db.Column(db.String(128))
    graduated_at = db.Column(db.DateTime)
    
    # Additional blockchain fields for Phase 2 integration
    creator_fees_accumulated = db.Column(db.Numeric(precision=20, scale=8), default=0)
    deployment_block_number = db.Column(db.Integer, nullable=True)
    nft_position_id = db.Column(db.Integer, nullable=True)
    liquidity_pool_address = db.Column(db.String(128), nullable=True)
    
    # IPFS storage
    ipfs_image_hash = db.Column(db.String(128))
    ipfs_metadata_hash = db.Column(db.String(128))
    ipfs_image_url = db.Column(db.String(256))
    ipfs_metadata_url = db.Column(db.String(256))
    
    # Metadata
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Social features
    view_count = db.Column(db.Integer, default=0)
    trade_count = db.Column(db.Integer, default=0)
    holder_count = db.Column(db.Integer, default=0)
    
    # Relationships
    trades = db.relationship('Trade', backref='token', lazy='dynamic')
    holdings = db.relationship('Holding', backref='token', lazy='dynamic')
    reserve_distributions = db.relationship('ReserveDistribution', backref='token', lazy='dynamic')
    
    @property
    def graduation_threshold(self):
        """Market cap threshold for graduation - pulls from platform settings"""
        settings = PlatformSettings.get_settings()
        return float(settings.graduation_threshold_usd)
    
    @property
    def progress_to_graduation(self):
        """Progress percentage to graduation"""
        if self.is_graduated:
            return 100
        return min((float(self.current_market_cap) / self.graduation_threshold) * 100, 100)
    
    def update_market_data(self, new_price, kas_reserve, token_reserve):
        """Update market data after trade"""
        self.current_price = new_price
        self.kas_reserve = kas_reserve
        self.token_reserve = token_reserve
        self.current_market_cap = new_price * self.circulating_supply if self.circulating_supply else 0
        self.updated_at = datetime.now(timezone.utc)
        
        # Check for graduation
        if not self.is_graduated and self.current_market_cap >= self.graduation_threshold:
            self.graduate_token()
    
    def graduate_token(self):
        """Mark token as graduated and update creator stats"""
        self.is_graduated = True
        self.graduated_at = datetime.now(timezone.utc)
        
        # Update creator's graduated tokens count (real-time stat)
        creator = User.query.get(self.creator_id)
        if creator:
            creator.total_graduated_tokens = (creator.total_graduated_tokens or 0) + 1
        
        # TODO: Trigger graduation to Kaspa Finance DEX
    
    def __repr__(self):
        return f'<Token {self.symbol}>'

class ReserveDistribution(db.Model):
    """Reserve token distribution tracking (PRO tokens only)"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Token reference
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    
    # Recipient details
    recipient_wallet = db.Column(db.String(128), nullable=False, index=True)
    allocation_type = db.Column(db.String(32), nullable=False)
    
    # Amount distributed
    amount = db.Column(db.Numeric(precision=30, scale=0), nullable=False)
    
    # Blockchain tracking
    tx_hash = db.Column(db.String(128), nullable=True)
    
    # Timestamps
    distributed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<ReserveDistribution {self.allocation_type} {self.amount} tokens to {self.recipient_wallet[:10]}...>'

class Trade(db.Model):
    """Trade model for bonding curve transactions"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Trade details
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    
    trade_type = db.Column(db.String(16), nullable=False)  # 'buy' or 'sell'
    kas_amount = db.Column(db.Numeric(precision=20, scale=8), nullable=False)
    token_amount = db.Column(db.Numeric(precision=30, scale=0), nullable=False)
    price_per_token = db.Column(db.Numeric(precision=20, scale=12), nullable=False)
    
    # Market state at time of trade
    market_cap_before = db.Column(db.Numeric(precision=20, scale=8))
    market_cap_after = db.Column(db.Numeric(precision=20, scale=8))
    
    # Blockchain info
    tx_hash = db.Column(db.String(128), unique=True, nullable=True)
    tx_status = db.Column(db.String(32), default='pending')  # pending, confirmed, failed
    
    # Fees
    platform_fee = db.Column(db.Numeric(precision=20, scale=8), default=0)  # 1% swap fee
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = db.Column(db.DateTime)
    
    def confirm_trade(self):
        """Confirm a trade and update user stats in real-time"""
        self.tx_status = 'confirmed'
        self.confirmed_at = datetime.now(timezone.utc)
        
        user = User.query.get(self.user_id)
        if user:
            user.total_trades_count = (user.total_trades_count or 0) + 1
            user.total_trading_volume = (user.total_trading_volume or 0) + self.kas_amount
    
    def __repr__(self):
        return f'<Trade {self.trade_type} {self.token_amount} tokens for {self.kas_amount} KAS>'

class Holding(db.Model):
    """User holdings for tokens"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    
    # Holdings
    token_amount = db.Column(db.Numeric(precision=30, scale=0), default=0)
    average_price = db.Column(db.Numeric(precision=20, scale=12), default=0)
    total_invested = db.Column(db.Numeric(precision=20, scale=8), default=0)
    
    # Metadata
    first_purchase = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_trade = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='holdings')
    
    # Unique constraint and indexes
    __table_args__ = (
        db.UniqueConstraint('user_id', 'token_id', name='unique_user_token'),
        db.Index('idx_holding_token_amount', 'token_id', 'token_amount'),
    )
    
    @property
    def current_value(self):
        """Current value of holdings"""
        token_obj = Token.query.get(self.token_id)
        if token_obj and self.token_amount:
            return float(self.token_amount) * float(token_obj.current_price)
        return 0
    
    @property
    def profit_loss(self):
        """Profit/loss on holdings"""
        return self.current_value - float(self.total_invested)
    
    @property
    def profit_loss_percentage(self):
        """Profit/loss percentage"""
        if self.total_invested and self.total_invested > 0:
            return (self.profit_loss / float(self.total_invested)) * 100
        return 0
    
    def update_holding(self, trade_amount, trade_price, kas_amount):
        """Update holding after trade"""
        if trade_amount > 0:  # Buy
            # Update average price
            total_tokens = float(self.token_amount) + float(trade_amount)
            total_investment = float(self.total_invested) + float(kas_amount)
            self.average_price = total_investment / total_tokens if total_tokens > 0 else 0
            
            self.token_amount = total_tokens
            self.total_invested = total_investment
        else:  # Sell
            # Reduce holdings proportionally
            sell_ratio = abs(float(trade_amount)) / float(self.token_amount) if self.token_amount > 0 else 0
            self.token_amount = float(self.token_amount) + float(trade_amount)  # trade_amount is negative for sells
            self.total_invested = float(self.total_invested) * (1 - sell_ratio)
        
        self.last_trade = datetime.now(timezone.utc)
    
    def __repr__(self):
        token_obj = Token.query.get(self.token_id)
        return f'<Holding {self.user.display_name} holds {self.token_amount} {token_obj.symbol if token_obj else "Unknown"}>'

class Achievement(db.Model):
    """Achievement system for gamification"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Achievement details
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(128))  # emoji or icon class
    category = db.Column(db.String(64))  # creator, trader, social, etc.
    
    # Requirements
    requirement_type = db.Column(db.String(64))  # tokens_created, trading_volume, etc.
    requirement_value = db.Column(db.Numeric(precision=20, scale=8))
    
    # Rewards
    gem_points_reward = db.Column(db.Integer, default=0)
    
    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Achievement {self.name}>'

class UserAchievement(db.Model):
    """User achievements (many-to-many)"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='earned_achievements')
    achievement = db.relationship('Achievement', backref='earned_by_users')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),)
    
    def __repr__(self):
        return f'<UserAchievement {self.user.display_name or self.user.wallet_address[:8]} earned {self.achievement.name}>'

class UserProfile(db.Model):
    """Extended user profile information for leaderboard"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Profile details
    bio = db.Column(db.Text)
    avatar_path = db.Column(db.String(256))  # New file path for compressed avatars
    avatar_updated_at = db.Column(db.DateTime)  # For cache busting
    username = db.Column(db.String(64), unique=True, nullable=True)  # Optional custom username
    
    # Social handles (verified)
    twitter_handle = db.Column(db.String(64))
    telegram_handle = db.Column(db.String(64))
    discord_handle = db.Column(db.String(64))
    
    # Verification status
    is_twitter_verified = db.Column(db.Boolean, default=False)
    is_telegram_verified = db.Column(db.Boolean, default=False)
    
    # Account type and status  
    account_type = db.Column(db.String(32), default='Standard')  # Standard, Premium, VIP
    member_since = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Privacy settings
    is_profile_public = db.Column(db.Boolean, default=True)
    show_wallet_address = db.Column(db.Boolean, default=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('profile', uselist=False))
    
    def __repr__(self):
        return f'<UserProfile {self.username or self.user.display_name}>'

class ConnectedWallet(db.Model):
    """Multiple wallet connections for users"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Wallet details
    wallet_address = db.Column(db.String(128), nullable=False, index=True)
    wallet_type = db.Column(db.String(32), nullable=False)  # kastle, metamask, etc.
    wallet_label = db.Column(db.String(64))  # User-defined label
    
    # Status
    is_primary = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    connected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='connected_wallets')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'wallet_address', name='unique_user_wallet'),)
    
    def __repr__(self):
        return f'<ConnectedWallet {self.wallet_address[:10]}... ({self.wallet_type})>'

class Referral(db.Model):
    """Referral tracking system"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Referrer and referee
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null until signup
    
    # Referral details
    referral_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    referral_link = db.Column(db.String(256))
    
    # Status and metrics
    status = db.Column(db.String(32), default='pending')  # pending, completed, rewarded
    clicks = db.Column(db.Integer, default=0)
    qualified_signups = db.Column(db.Integer, default=0)
    
    # Rewards
    points_earned = db.Column(db.Integer, default=0)
    is_rewarded = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referee = db.relationship('User', foreign_keys=[referee_id], backref='referral_used')
    
    def __repr__(self):
        return f'<Referral {self.referral_code} by {self.referrer.display_name}>'

class Activity(db.Model):
    """User activity tracking for leaderboard"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Activity details
    activity_type = db.Column(db.String(64), nullable=False)  # token_created, trade_buy, trade_sell, achievement_earned, etc.
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    
    # Related entities
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=True)
    
    # Activity metadata
    points_earned = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user = db.relationship('User', backref='activities')
    token = db.relationship('Token', backref='related_activities')
    trade = db.relationship('Trade', backref='activity_log')
    achievement = db.relationship('Achievement', backref='activity_mentions')
    
    def __repr__(self):
        return f'<Activity {self.activity_type} by {self.user.display_name}>'

class TrendCache(db.Model):
    """Trend cache for Gemmy Zeroday Memification Engine"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Cache metadata
    cache_type = db.Column(db.String(32), nullable=False)  # 'external_trends' or 'kaspa_tech'
    
    # Scraped data (JSON format)
    trends_data = db.Column(db.JSON)  # Raw scraped memes from 4chan/Reddit
    scored_trends = db.Column(db.JSON)  # AI-scored and ranked trends
    
    # Kaspa tech meme suggestions
    kaspa_memes = db.Column(db.JSON)  # Tech-based meme suggestions
    
    # Cache control
    scraped_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = db.Column(db.DateTime, index=True)  # Auto-expires after 12 hours
    is_valid = db.Column(db.Boolean, default=True)
    
    # Stats
    usage_count = db.Column(db.Integer, default=0)  # Track how many times used
    
    @classmethod
    def get_or_refresh(cls, cache_type='external_trends'):
        """Get valid cache or return None if refresh needed"""
        cache = cls.query.filter_by(
            cache_type=cache_type,
            is_valid=True
        ).filter(
            cls.expires_at > datetime.now(timezone.utc)
        ).order_by(cls.scraped_at.desc()).first()
        
        if cache:
            cache.usage_count += 1
            db.session.commit()
            return cache
        return None
    
    @classmethod
    def cleanup_old_entries(cls):
        """Remove entries older than 24 hours (auto-cleanup)"""
        from datetime import timedelta
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        old_entries = cls.query.filter(cls.scraped_at < cutoff_time).delete()
        db.session.commit()
        return old_entries
    
    def __repr__(self):
        return f'<TrendCache {self.cache_type} at {self.scraped_at}>'

class Airdrop(db.Model):
    """Airdrop campaigns for PRO tokens"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Airdrop details
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Airdrop configuration
    airdrop_type = db.Column(db.String(32), nullable=False)  # random_raffle, top_contributors, active_chatters, token_holders, early_supporters
    total_amount = db.Column(db.Numeric(precision=30, scale=0), nullable=False)
    
    # Type-specific parameters (stored as JSON for flexibility)
    parameters = db.Column(db.JSON)  # {winners: 10, min_balance: 1000, etc.}
    
    # Status tracking
    status = db.Column(db.String(32), default='pending')  # pending, processing, completed, failed
    recipient_count = db.Column(db.Integer, default=0)
    distributed_amount = db.Column(db.Numeric(precision=30, scale=0), default=0)
    
    # Transaction info
    tx_hash = db.Column(db.String(128))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    token = db.relationship('Token', backref='airdrops')
    creator = db.relationship('User', backref='created_airdrops')
    
    def __repr__(self):
        return f'<Airdrop {self.airdrop_type} for {self.token.symbol}>'

class AirdropRecipient(db.Model):
    """Track individual airdrop recipients"""
    id = db.Column(db.Integer, primary_key=True)
    
    airdrop_id = db.Column(db.Integer, db.ForeignKey('airdrop.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Amount received
    amount_received = db.Column(db.Numeric(precision=30, scale=0), nullable=False)
    
    # Claim status
    is_claimed = db.Column(db.Boolean, default=False)
    claimed_at = db.Column(db.DateTime)
    claim_tx_hash = db.Column(db.String(128))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    airdrop = db.relationship('Airdrop', backref='recipients')
    user = db.relationship('User', backref='received_airdrops')
    
    # Unique constraint: one airdrop entry per user per airdrop
    __table_args__ = (db.UniqueConstraint('airdrop_id', 'user_id', name='unique_airdrop_recipient'),)
    
    def __repr__(self):
        return f'<AirdropRecipient {self.user.wallet_address[:8]} from {self.airdrop.token.symbol}>'

class TokenEngagement(db.Model):
    """Track user engagement with specific tokens and token-specific community points"""
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    
    # Engagement metrics
    community_points = db.Column(db.Integer, default=0)  # Token-specific points
    messages_sent = db.Column(db.Integer, default=0)
    trades_count = db.Column(db.Integer, default=0)
    total_traded_volume = db.Column(db.Numeric(precision=20, scale=8), default=0)
    polls_created = db.Column(db.Integer, default=0)
    polls_voted = db.Column(db.Integer, default=0)
    spotlight_messages = db.Column(db.Integer, default=0)
    
    # Holding info
    current_balance = db.Column(db.Numeric(precision=30, scale=0), default=0)
    first_acquired_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='token_engagements')
    token = db.relationship('Token', backref='user_engagements')
    
    # Unique constraint: one engagement record per user per token
    __table_args__ = (db.UniqueConstraint('user_id', 'token_id', name='unique_user_token_engagement'),)
    
    def add_community_points(self, points, activity_type='general'):
        """Add community points for this token engagement"""
        self.community_points = (self.community_points or 0) + points
        self.last_activity_at = datetime.now(timezone.utc)
        db.session.commit()
    
    @classmethod
    def get_or_create(cls, user_id, token_id):
        """Get existing engagement or create new one"""
        engagement = cls.query.filter_by(user_id=user_id, token_id=token_id).first()
        if not engagement:
            engagement = cls(user_id=user_id, token_id=token_id)
            db.session.add(engagement)
            db.session.commit()
        return engagement
    
    def __repr__(self):
        return f'<TokenEngagement {self.user.wallet_address[:8]} with {self.token.symbol}>'

class LinkedWallet(db.Model):
    """Secondary wallet addresses linked to a user's primary account"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Primary wallet owner
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Linked wallet details
    wallet_address = db.Column(db.String(128), unique=True, nullable=False, index=True)
    wallet_label = db.Column(db.String(128), nullable=True)
    
    # Security and verification
    signature_payload = db.Column(db.Text, nullable=True)
    last_verified_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default='pending', nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    @property
    def is_verified(self):
        """Check if wallet is verified"""
        return self.status == 'verified'
    
    def __repr__(self):
        return f'<LinkedWallet {self.wallet_address[:10]}... ({self.status})>'

class WalletVerificationChallenge(db.Model):
    """Temporary verification challenges for linking secondary wallets"""
    id = db.Column(db.Integer, primary_key=True)
    
    # User requesting verification
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Wallet being verified
    wallet_address = db.Column(db.String(128), nullable=False, index=True)
    
    # Challenge details
    nonce = db.Column(db.String(128), unique=True, nullable=False, index=True)
    challenge_message = db.Column(db.Text, nullable=False)
    
    # Security
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='verification_challenges')
    
    @property
    def is_expired(self):
        """Check if challenge has expired"""
        # Ensure expires_at is timezone-aware for comparison
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at
    
    def mark_used(self):
        """Mark challenge as used to prevent replay attacks"""
        self.used = True
        db.session.commit()
    
    @classmethod
    def create_challenge(cls, user_id, wallet_address):
        """Create a new verification challenge with 10-minute expiration"""
        nonce = secrets.token_hex(32)
        challenge_message = f"Sign this message to link wallet {wallet_address} to your account.\n\nNonce: {nonce}\nTimestamp: {int(datetime.now(timezone.utc).timestamp())}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        challenge = cls(
            user_id=user_id,
            wallet_address=wallet_address.lower(),
            nonce=nonce,
            challenge_message=challenge_message,
            expires_at=expires_at
        )
        db.session.add(challenge)
        db.session.commit()
        return challenge
    
    def __repr__(self):
        return f'<WalletVerificationChallenge {self.wallet_address[:10]}... ({"expired" if self.is_expired else "active"})>'

# DEPRECATED: ClaimOwnershipChallenge model removed
# The claim_ownership_challenge table still exists in the database to preserve historical data (14 records)
# but is no longer used. The functionality has been replaced by TransferRequest which provides
# a cleaner approval flow. The old system allowed aggressive wallet takeovers by proving ownership,
# while the new system requires the wallet owner to approve transfer requests.

class TransferRequest(db.Model):
    """Request to transfer/link a wallet from one user to another"""
    id = db.Column(db.Integer, primary_key=True)
    
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    wallet_address = db.Column(db.String(128), nullable=False, index=True)
    status = db.Column(db.String(32), default='pending', nullable=False, index=True)
    nonce = db.Column(db.String(128), unique=True, nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    
    requester = db.relationship('User', foreign_keys=[requester_id], backref='transfer_requests_made')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='transfer_requests_received')
    
    @property
    def is_expired(self):
        """Check if request has expired"""
        # Ensure expires_at is timezone-aware for comparison
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at
    
    def accept(self):
        """Accept the transfer request with atomic expiry validation
        
        This provides defense-in-depth against race conditions by validating
        expiry one final time at the exact moment of state change.
        
        Raises:
            ValueError: If request has expired or is not in pending status
        
        Note: Does NOT commit - caller must handle transaction commit for atomicity
        """
        # SECURITY: Atomic expiry check at the exact moment of acceptance
        # This is the final defense against time-of-check-time-of-use vulnerabilities
        if self.is_expired:
            self.status = 'expired'
            raise ValueError(f'Transfer request has expired (expired at {self.expires_at})')
        
        if self.status != 'pending':
            raise ValueError(f'Transfer request is not pending (status: {self.status})')
        
        self.status = 'accepted'
    
    def decline(self):
        """Decline the transfer request"""
        self.status = 'declined'
        db.session.commit()
    
    def expire(self):
        """Mark request as expired"""
        self.status = 'expired'
        db.session.commit()
    
    @classmethod
    def create_request(cls, requester_id, owner_id, wallet_address):
        """Create a new transfer request with 24-hour expiration"""
        nonce = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        request = cls(
            requester_id=requester_id,
            owner_id=owner_id,
            wallet_address=wallet_address.lower(),
            nonce=nonce,
            expires_at=expires_at
        )
        db.session.add(request)
        db.session.commit()
        return request
    
    def __repr__(self):
        return f'<TransferRequest {self.wallet_address[:10]}... ({self.status})>'

class TradeEvent(db.Model):
    """Blockchain trade events from BondingCurvePool smart contract"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Trade details
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    user_wallet_address = db.Column(db.String(128), nullable=False, index=True)
    trade_type = db.Column(db.String(16), nullable=False)
    
    # Amounts
    kas_amount = db.Column(db.Numeric(precision=20, scale=8), nullable=False)
    token_amount = db.Column(db.Numeric(precision=30, scale=0), nullable=False)
    
    # Fees
    platform_fee = db.Column(db.Numeric(precision=20, scale=8), default=0)
    creator_fee = db.Column(db.Numeric(precision=20, scale=8), default=0)
    anti_bot_fee = db.Column(db.Numeric(precision=20, scale=8), default=0)
    
    # Blockchain info
    tx_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    block_number = db.Column(db.Integer, nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    
    # Indexing metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    token = db.relationship('Token', backref='trade_events')
    
    def __repr__(self):
        return f'<TradeEvent {self.trade_type} {self.token_amount} tokens for {self.kas_amount} KAS>'

class AntiBotFeeTracker(db.Model):
    """Track anti-bot fee distribution (70% Airdrop Treasury, 30% Platform Dev)"""
    id = db.Column(db.Integer, primary_key=True)
    
    # References
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    trade_event_id = db.Column(db.Integer, db.ForeignKey('trade_event.id'), nullable=False)
    
    # Fee breakdown
    total_anti_bot_fee = db.Column(db.Numeric(precision=20, scale=8), nullable=False)
    airdrop_treasury_amount = db.Column(db.Numeric(precision=20, scale=8), nullable=False)
    platform_dev_amount = db.Column(db.Numeric(precision=20, scale=8), nullable=False)
    
    # Blockchain info
    tx_hash = db.Column(db.String(128), nullable=False, index=True)
    block_number = db.Column(db.Integer, nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    
    # Indexing metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    token = db.relationship('Token', backref='anti_bot_fees')
    trade_event = db.relationship('TradeEvent', backref='anti_bot_fee_split')
    
    def __repr__(self):
        return f'<AntiBotFeeTracker {self.total_anti_bot_fee} KAS - 70/30 split>'

class PendingTransaction(db.Model):
    """Pending blockchain transactions for monitoring"""
    __tablename__ = 'pending_transaction'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Transaction details
    tx_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    tx_type = db.Column(db.String(50))  # 'buy', 'sell', 'claim_fees', 'distribute_fees', 'deploy_token'
    user_address = db.Column(db.String(128), index=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=True, index=True)
    
    # Transaction status
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'confirmed', 'failed'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    confirmed_at = db.Column(db.DateTime)
    
    # Blockchain confirmation details
    block_number = db.Column(db.Integer)
    gas_used = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    
    # Relationships
    token = db.relationship('Token', backref='pending_transactions')
    
    # Composite index for efficient queries
    __table_args__ = (
        db.Index('idx_pending_tx_status_time', 'status', 'created_at'),
    )
    
    def __repr__(self):
        return f'<PendingTransaction {self.tx_hash[:10]}... ({self.status})>'

class PlatformSettings(db.Model):
    """Platform-wide configuration settings"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Graduation settings
    graduation_threshold_usd = db.Column(db.Numeric(precision=20, scale=2), default=200.00)  # $200 for testnet
    
    # Network info (for display purposes)
    network = db.Column(db.String(32), default='testnet')  # testnet or mainnet
    
    # Metadata
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(128))  # wallet address of admin who updated
    
    @staticmethod
    def get_settings():
        """Get or create platform settings"""
        settings = PlatformSettings.query.first()
        if not settings:
            settings = PlatformSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def __repr__(self):
        return f'<PlatformSettings threshold=${self.graduation_threshold_usd}>'