import os
from datetime import datetime, timezone
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
    
    # Relationships
    tokens_created = db.relationship('Token', backref='creator', lazy='dynamic')
    trades = db.relationship('Trade', backref='user', lazy='dynamic')
    
    def add_gem_points(self, points):
        """Add GEM points to user"""
        self.gem_points = (self.gem_points or 0) + points
        db.session.commit()
    
    @classmethod
    def get_or_create_by_wallet(cls, wallet_address, wallet_type=None, display_name=None):
        """Get existing user or create new one by wallet address"""
        user = cls.query.filter_by(wallet_address=wallet_address.lower()).first()
        if not user:
            user = cls(
                wallet_address=wallet_address.lower(),
                wallet_type=wallet_type,
                display_name=display_name or f"User-{wallet_address[:8]}"
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update last seen
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
    
    # Token configuration
    total_supply = db.Column(db.Numeric(precision=30, scale=0), default=1000000000)  # 1B default
    reserved_tokens = db.Column(db.Numeric(precision=30, scale=0), default=0)
    reserved_percentage = db.Column(db.Float, default=0.0)  # 0-25%
    
    # Blockchain info
    contract_address = db.Column(db.String(128), unique=True, nullable=True, index=True)
    deployment_tx = db.Column(db.String(128))
    deployment_status = db.Column(db.String(32), default='pending')  # pending, deploying, deployed, failed
    
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
    
    @property
    def graduation_threshold(self):
        """Market cap threshold for graduation (~$70K)"""
        return 70000
    
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
        """Mark token as graduated"""
        self.is_graduated = True
        self.graduated_at = datetime.now(timezone.utc)
        # TODO: Trigger graduation to Kaspa Finance DEX
    
    def __repr__(self):
        return f'<Token {self.symbol}>'

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
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'token_id', name='unique_user_token'),)
    
    @property
    def current_value(self):
        """Current value of holdings"""
        if self.token and self.token_amount:
            return float(self.token_amount) * float(self.token.current_price)
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
        return f'<Holding {self.user.username} holds {self.token_amount} {self.token.symbol}>'

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
    profile_picture_url = db.Column(db.String(512))
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='activities')
    token = db.relationship('Token', backref='related_activities')
    trade = db.relationship('Trade', backref='activity_log')
    achievement = db.relationship('Achievement', backref='activity_mentions')
    
    def __repr__(self):
        return f'<Activity {self.activity_type} by {self.user.display_name}>'