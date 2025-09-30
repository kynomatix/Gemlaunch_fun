"""
Token Service Layer
Handles all token-related business logic including creation, management, and market data.
"""

import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from flask import current_app
import logging

from models import db, Token, Holding, Activity
from models_extended import ChatMessage, Poll, TokenLeaderboard, TokenSettings

logger = logging.getLogger(__name__)


class TokenService:
    """Service class for token-related operations"""
    
    @staticmethod
    def create_token(user, token_data: Dict[str, Any]) -> Optional[Token]:
        """
        Create a new token with the provided data.
        
        Args:
            user: The user creating the token
            token_data: Dictionary containing token information including:
                - name: Token name
                - symbol: Token symbol
                - description: Token description (optional)
                - website: Website URL (optional)
                - twitter: Twitter URL (optional)
                - telegram: Telegram URL (optional)
                - total_supply: Total supply (default: 1000000000)
                - reserved_percentage: Reserved percentage for treasury/LP/airdrops (0-25%)
                
        Returns:
            Token: The created token object or None if creation failed
        """
        try:
            # Create new token instance
            new_token = Token()
            
            # Set basic token information
            new_token.name = token_data.get('name', '')
            new_token.symbol = token_data.get('symbol', '').upper()
            new_token.description = token_data.get('description', '')
            
            # Set social links
            new_token.website = token_data.get('website', '')
            new_token.twitter = token_data.get('twitter', '')
            new_token.telegram = token_data.get('telegram', '')
            
            # Set creator
            new_token.creator_id = user.id
            
            # Set token configuration
            new_token.total_supply = int(token_data.get('total_supply', 1000000000))
            new_token.reserved_percentage = float(token_data.get('reserved_percentage', 0))
            
            # Calculate reserved tokens based on percentage
            if new_token.reserved_percentage > 0:
                new_token.reserved_tokens = int(new_token.total_supply * (new_token.reserved_percentage / 100))
            else:
                new_token.reserved_tokens = 0
            
            # Set initial market data
            new_token.circulating_supply = 0
            new_token.current_price = 0.001  # Starting price
            new_token.current_market_cap = 1000  # Start at $1K market cap
            new_token.deployment_status = 'pending'  # Initial status
            
            # Generate mock contract address (for UI demo purposes)
            new_token.contract_address = f'0x{secrets.token_hex(20).lower()}'
            
            # Add to database and flush to get the ID
            db.session.add(new_token)
            db.session.flush()  # Flush to get the token ID
            
            # Create default token settings with the token ID
            token_settings = TokenSettings(token_id=new_token.id)
            db.session.add(token_settings)
            
            # Update user statistics
            user.total_tokens_created = (user.total_tokens_created or 0) + 1
            user.add_gem_points(100)  # Award points for token creation
            
            # Record activity
            activity = Activity(
                user_id=user.id,
                activity_type='token_created',
                title=f'Token Created: {new_token.symbol}',
                description=f'Created token {new_token.name} ({new_token.symbol})',
                token_id=new_token.id,
                points_earned=100
            )
            db.session.add(activity)
            
            # Commit all changes
            db.session.commit()
            
            logger.info(f"Token {new_token.symbol} created successfully by user {user.id}")
            return new_token
            
        except Exception as e:
            logger.error(f"Error creating token: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def is_pro_token(token: Token) -> bool:
        """
        Determine if a token is a 'pro' token.
        Single source of truth: A token is 'pro' if it has reserved tokens (reserved_percentage > 0)
        
        Args:
            token: The token to check
            
        Returns:
            bool: True if the token is a pro token, False otherwise
        """
        if not token:
            return False
        
        return token.reserved_percentage > 0
    
    @staticmethod
    def get_token_details(contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a token including market data and metrics.
        
        Args:
            contract_address: The contract address of the token
            
        Returns:
            dict: Token details including all relevant information or None if not found
        """
        try:
            # Query token with related data
            token = Token.query.filter_by(contract_address=contract_address).first()
            
            if not token:
                return None
            
            # Calculate additional metrics
            is_pro = TokenService.is_pro_token(token)
            progress_to_graduation = token.progress_to_graduation
            
            # Get holder count
            holder_count = Holding.query.filter(
                Holding.token_id == token.id,
                Holding.token_amount > 0
            ).count()
            
            # Get chat message count
            message_count = ChatMessage.query.filter_by(
                token_id=token.id,
                is_deleted=False
            ).count()
            
            # Get active polls count
            active_polls = Poll.query.filter_by(
                token_id=token.id,
                is_active=True
            ).count()
            
            # Prepare token details
            token_details = {
                'id': token.id,
                'name': token.name,
                'symbol': token.symbol,
                'description': token.description,
                'image_url': token.image_url,
                
                # Social links
                'website': token.website,
                'twitter': token.twitter,
                'telegram': token.telegram,
                
                # Token configuration
                'total_supply': float(token.total_supply),
                'reserved_tokens': float(token.reserved_tokens),
                'reserved_percentage': token.reserved_percentage,
                'is_pro_token': is_pro,
                
                # Blockchain info
                'contract_address': token.contract_address,
                'deployment_status': token.deployment_status,
                'deployment_tx': token.deployment_tx,
                
                # Market data
                'current_price': float(token.current_price) if token.current_price else 0,
                'current_market_cap': float(token.current_market_cap) if token.current_market_cap else 0,
                'circulating_supply': float(token.circulating_supply) if token.circulating_supply else 0,
                'trading_volume_24h': float(token.trading_volume_24h) if token.trading_volume_24h else 0,
                
                # Bonding curve state
                'kas_reserve': float(token.kas_reserve) if token.kas_reserve else 0,
                'token_reserve': float(token.token_reserve) if token.token_reserve else 0,
                'is_graduated': token.is_graduated,
                'graduation_progress': progress_to_graduation,
                'graduation_threshold': token.graduation_threshold,
                
                # Social metrics
                'view_count': token.view_count,
                'trade_count': token.trade_count,
                'holder_count': holder_count,
                'message_count': message_count,
                'active_polls': active_polls,
                
                # Creator info
                'creator_id': token.creator_id,
                'creator_address': token.creator.wallet_address if token.creator else None,
                'creator_name': token.creator.display_name if token.creator else None,
                
                # Timestamps
                'created_at': token.created_at.isoformat() if token.created_at else None,
                'updated_at': token.updated_at.isoformat() if token.updated_at else None,
                'graduated_at': token.graduated_at.isoformat() if token.graduated_at else None
            }
            
            return token_details
            
        except Exception as e:
            logger.error(f"Error getting token details for {contract_address}: {str(e)}")
            return None
    
    @staticmethod
    def update_token_settings(token: Token, settings: Dict[str, Any]) -> bool:
        """
        Update token settings including chat settings, voting requirements, etc.
        
        Args:
            token: The token to update settings for
            settings: Dictionary containing settings to update:
                - chat_enabled: Enable/disable chat
                - chat_holders_only: Require token holding to chat (maps to holders_only_chat field)
                - min_tokens_to_chat: Minimum tokens required to chat
                - spotlight_enabled: Enable spotlight messages
                - spotlight_cost: Cost for spotlight messages
                - polls_enabled: Enable polls
                - min_tokens_to_vote: Minimum tokens to vote
                
        Returns:
            bool: True if settings were updated successfully, False otherwise
        """
        try:
            # Get or create token settings
            token_settings = TokenSettings.query.filter_by(token_id=token.id).first()
            if not token_settings:
                token_settings = TokenSettings(token_id=token.id)
                db.session.add(token_settings)
            
            # Update settings based on provided data
            if 'chat_enabled' in settings:
                token_settings.chat_enabled = bool(settings['chat_enabled'])
            
            if 'chat_holders_only' in settings:
                token_settings.holders_only_chat = bool(settings['chat_holders_only'])
            
            if 'min_tokens_to_chat' in settings:
                token_settings.min_tokens_to_chat = int(settings['min_tokens_to_chat'])
            
            if 'min_tokens_for_spotlight' in settings:
                token_settings.min_tokens_for_spotlight = int(settings['min_tokens_for_spotlight'])
            
            if 'polls_enabled' in settings:
                token_settings.polls_enabled = bool(settings['polls_enabled'])
            
            if 'min_tokens_to_vote' in settings:
                token_settings.min_tokens_to_vote = int(settings['min_tokens_to_vote'])
            
            # Update timestamp
            token_settings.updated_at = datetime.now(timezone.utc)
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"Token settings updated successfully for token {token.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating token settings: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def update_market_data(token: Token, new_price: float, kas_reserve: float, token_reserve: float) -> bool:
        """
        Update token market data after a trade.
        
        Args:
            token: The token to update
            new_price: New price per token
            kas_reserve: Updated KAS reserve in bonding curve
            token_reserve: Updated token reserve in bonding curve
            
        Returns:
            bool: True if market data was updated successfully, False otherwise
        """
        try:
            # Update price and reserves
            token.current_price = new_price
            token.kas_reserve = kas_reserve
            token.token_reserve = token_reserve
            
            # Recalculate market cap
            if token.circulating_supply:
                token.current_market_cap = new_price * float(token.circulating_supply)
            else:
                token.current_market_cap = 0
            
            # Update timestamp
            token.updated_at = datetime.now(timezone.utc)
            
            # Check for graduation (market cap >= $70K)
            if not token.is_graduated and token.current_market_cap >= token.graduation_threshold:
                token.is_graduated = True
                token.graduated_at = datetime.now(timezone.utc)
                logger.info(f"Token {token.symbol} has graduated with market cap ${token.current_market_cap}")
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"Market data updated for token {token.symbol}: price={new_price}, market_cap={token.current_market_cap}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating market data: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def ensure_token_settings(token: Token) -> TokenSettings:
        """
        Ensure a token has settings, creating them if they don't exist.
        
        Args:
            token: The token to ensure settings for
            
        Returns:
            TokenSettings: The token's settings object
        """
        if not token.settings:
            token_settings = TokenSettings(token_id=token.id)
            db.session.add(token_settings)
            db.session.commit()
            return token_settings
        return token.settings