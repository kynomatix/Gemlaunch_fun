"""
Holder Service Layer
Handles token holder verification and balance queries via blockchain.
Replaces database Holding model with on-chain data.
"""

import logging
from typing import Optional, Dict, Any
from web3 import Web3

logger = logging.getLogger(__name__)


class HolderService:
    """Service class for token holder verification using blockchain data"""
    
    @staticmethod
    def user_holds_min_tokens(
        wallet_address: str, 
        token_address: str, 
        min_amount: float
    ) -> bool:
        """
        Check if a wallet holds at least the minimum amount of tokens.
        Queries blockchain directly via web3.
        
        Args:
            wallet_address: User's wallet address (e.g., 0x...)
            token_address: Token contract address (e.g., 0x...)
            min_amount: Minimum token amount required
            
        Returns:
            bool: True if user holds >= min_amount tokens, False otherwise
        """
        balance = HolderService.get_user_balance(wallet_address, token_address)
        return balance >= min_amount
    
    @staticmethod
    def get_user_balance(
        wallet_address: str,
        token_address: str
    ) -> float:
        """
        Get user's token balance directly from blockchain via web3.
        Uses global Flask-Caching instance with 10-second timeout.
        
        Args:
            wallet_address: User's wallet address
            token_address: Token contract address
            
        Returns:
            float: User's token balance (0 if not found or error)
        """
        from flask import current_app
        
        # Use global cache instance from app.py
        cache = current_app.extensions.get('cache')
        if not cache:
            logger.warning("⚠️  Cache not configured, querying blockchain directly")
        
        cache_key = f"balance_{wallet_address}_{token_address}".lower()
        
        # Check cache first
        if cache:
            cached_balance = cache.get(cache_key)
            if cached_balance is not None:
                logger.debug(f"✅ Cache hit for balance: {cached_balance}")
                return float(cached_balance)
        
        try:
            # Query blockchain directly via web3
            from services.web3_service import get_web3_service
            web3_service = get_web3_service()
            
            # Get BondingCurvePool contract (which IS the ERC20 token)
            pool = web3_service.get_bonding_pool_contract(token_address)
            
            # Query balanceOf for the wallet
            balance_wei = pool.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()
            
            # Convert from Wei (18 decimals) to tokens
            balance = float(balance_wei) / 1e18
            
            # Cache for 10 seconds
            if cache:
                cache.set(cache_key, balance, timeout=10)
            
            logger.info(f"✅ Balance fetched: {wallet_address[:10]}... = {balance} tokens")
            return balance
            
        except Exception as e:
            logger.error(f"❌ Balance fetch failed for {wallet_address[:10]}...: {type(e).__name__}: {str(e)}")
            return 0.0
    
    @staticmethod
    def get_user_holding_info(
        wallet_address: str,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Get user's holding information (for API responses).
        
        Args:
            wallet_address: User's wallet address
            token_address: Token contract address
            
        Returns:
            dict: {
                'balance': float,
                'isHolder': bool,
                'wallet': str
            }
        """
        balance = HolderService.get_user_balance(wallet_address, token_address)
        
        return {
            'balance': balance,
            'isHolder': balance > 0,
            'wallet': wallet_address
        }
