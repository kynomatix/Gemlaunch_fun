"""Extended models for chat, polls, and token-specific features"""
from datetime import datetime, timezone
from models import db, Base

class ChatMessage(db.Model):
    """Chat messages per token"""
    __tablename__ = 'chat_message'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Message content
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(32), default='regular')  # regular, spotlight, announcement
    
    # Reply functionality
    reply_to_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=True)
    
    # Message metadata
    is_pinned = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    is_holders_only = db.Column(db.Boolean, default=False)
    
    # Engagement metrics
    love_count = db.Column(db.Integer, default=0)
    reply_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    edited_at = db.Column(db.DateTime)
    
    # Relationships
    token = db.relationship('Token', backref='chat_messages')
    user = db.relationship('User', backref='chat_messages')
    reactions = db.relationship('MessageReaction', backref='message', lazy='dynamic', cascade='all, delete-orphan')
    reply_to = db.relationship('ChatMessage', remote_side=[id], backref='replies')
    
    # Composite index for efficient message retrieval
    __table_args__ = (
        db.Index('idx_chat_token_time', 'token_id', 'created_at'),
    )
    
    def __repr__(self):
        return f'<ChatMessage {self.id} in {self.token.symbol}>'

class MessageReaction(db.Model):
    """User reactions to chat messages"""
    __tablename__ = 'message_reaction'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    reaction_type = db.Column(db.String(32), default='love')  # love, like, fire, etc.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Unique constraint - one reaction per user per message
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='unique_user_message_reaction'),)
    
    def __repr__(self):
        return f'<MessageReaction {self.reaction_type} on message {self.message_id}>'

class Poll(db.Model):
    """Token-specific polls"""
    __tablename__ = 'poll'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Poll content
    question = db.Column(db.String(500), nullable=False)
    poll_type = db.Column(db.String(32), default='single')  # single, multiple
    
    # Poll settings
    min_tokens_to_vote = db.Column(db.Numeric(precision=30, scale=0), default=0)
    vote_cost = db.Column(db.Numeric(precision=30, scale=0), default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ends_at = db.Column(db.DateTime)
    
    # Relationships
    token = db.relationship('Token', backref='polls')
    creator = db.relationship('User', backref='created_polls')
    options = db.relationship('PollOption', backref='poll', lazy='select', cascade='all, delete-orphan')
    
    @property
    def total_votes(self):
        return sum(option.vote_count for option in self.options)
    
    def __repr__(self):
        return f'<Poll {self.question[:50]}...>'

class PollOption(db.Model):
    """Options for polls"""
    __tablename__ = 'poll_option'
    
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id', ondelete='CASCADE'), nullable=False)
    
    option_text = db.Column(db.String(200), nullable=False)
    vote_count = db.Column(db.Integer, default=0)
    
    # Relationships
    votes = db.relationship('PollVote', backref='option', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PollOption {self.option_text}>'

class PollVote(db.Model):
    """User votes on polls"""
    __tablename__ = 'poll_vote'
    
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Vote metadata
    vote_weight = db.Column(db.Numeric(precision=20, scale=8), default=1)  # For weighted voting
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Unique constraint - one vote per user per poll
    __table_args__ = (db.UniqueConstraint('poll_id', 'user_id', name='unique_user_poll_vote'),)
    
    # Relationships
    poll = db.relationship('Poll', backref='votes')
    user = db.relationship('User', backref='poll_votes')
    
    def __repr__(self):
        return f'<PollVote user {self.user_id} on poll {self.poll_id}>'

class TokenAccolade(db.Model):
    """Token-specific accolades/achievements"""
    __tablename__ = 'token_accolade'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    
    # Accolade details
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(128))  # emoji or icon
    category = db.Column(db.String(64))  # governance, liquidity, community, etc.
    
    # Requirements and rewards
    requirement_type = db.Column(db.String(64))  # holds_amount, trades_count, etc.
    requirement_value = db.Column(db.Numeric(precision=20, scale=8))
    points_reward = db.Column(db.Integer, default=100)
    
    # Settings
    is_active = db.Column(db.Boolean, default=True)
    is_pro_only = db.Column(db.Boolean, default=False)  # Only for Pro tokens
    awards_leaderboard_points = db.Column(db.Boolean, default=True)  # Whether it counts for global leaderboard
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    token = db.relationship('Token', backref='accolades')
    
    # Unique constraint - unique name per token
    __table_args__ = (db.UniqueConstraint('token_id', 'name', name='unique_token_accolade'),)
    
    def __repr__(self):
        return f'<TokenAccolade {self.name} for {self.token.symbol}>'

class UserTokenAccolade(db.Model):
    """Users earning token-specific accolades"""
    __tablename__ = 'user_token_accolade'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    accolade_id = db.Column(db.Integer, db.ForeignKey('token_accolade.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)  # Denormalized for easier queries
    
    # Earning details
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    points_awarded = db.Column(db.Integer, default=0)
    
    # Relationships
    user = db.relationship('User', backref='token_accolades')
    accolade = db.relationship('TokenAccolade', backref='earned_by')
    token = db.relationship('Token', backref='user_accolades')
    
    # Unique constraint - one accolade per user per token accolade
    __table_args__ = (db.UniqueConstraint('user_id', 'accolade_id', name='unique_user_token_accolade'),)
    
    def __repr__(self):
        return f'<UserTokenAccolade {self.user.display_name} earned {self.accolade.name}>'

class TokenSettings(db.Model):
    """Token-specific settings (controlled by creator)"""
    __tablename__ = 'token_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, unique=True)
    
    # Chat settings
    holders_only_chat = db.Column(db.Boolean, default=False)
    min_tokens_to_chat = db.Column(db.Numeric(precision=30, scale=0), default=0)
    min_tokens_for_spotlight = db.Column(db.Numeric(precision=30, scale=0), default=500)
    
    # Poll settings
    min_tokens_to_create_poll = db.Column(db.Numeric(precision=30, scale=0), default=1000)
    poll_creation_cost = db.Column(db.Numeric(precision=30, scale=0), default=0)
    
    # Pro token settings (only for advanced tokens)
    dao_voting_threshold = db.Column(db.Numeric(precision=30, scale=0), default=10000)
    treasury_allocation_percent = db.Column(db.Float, default=15.0)
    airdrop_pool_percent = db.Column(db.Float, default=5.0)
    liquidity_rewards_enabled = db.Column(db.Boolean, default=False)
    
    # Feature toggles
    chat_enabled = db.Column(db.Boolean, default=True)
    polls_enabled = db.Column(db.Boolean, default=True)
    accolades_enabled = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    token = db.relationship('Token', backref=db.backref('settings', uselist=False))
    
    def __repr__(self):
        return f'<TokenSettings for {self.token.symbol}>'

class TokenLeaderboard(db.Model):
    """Token-specific leaderboard entries"""
    __tablename__ = 'token_leaderboard'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Points and ranking
    points = db.Column(db.Integer, default=0)
    rank = db.Column(db.Integer)
    
    # Activity metrics
    messages_sent = db.Column(db.Integer, default=0)
    reactions_given = db.Column(db.Integer, default=0)
    reactions_received = db.Column(db.Integer, default=0)
    polls_created = db.Column(db.Integer, default=0)
    votes_cast = db.Column(db.Integer, default=0)
    accolades_earned = db.Column(db.Integer, default=0)
    
    # Timestamps
    first_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    token = db.relationship('Token', backref='leaderboard_entries')
    user = db.relationship('User', backref='token_leaderboards')
    
    # Unique constraint and composite index
    __table_args__ = (
        db.UniqueConstraint('token_id', 'user_id', name='unique_token_user_leaderboard'),
        db.Index('idx_leaderboard_ranking', 'token_id', 'points'),
    )
    
    def add_points(self, points):
        """Add points to user's token-specific score"""
        self.points = (self.points or 0) + points
        self.last_activity = datetime.now(timezone.utc)
    
    def __repr__(self):
        return f'<TokenLeaderboard {self.user.display_name} in {self.token.symbol}: {self.points} pts>'