"""
MEV Protection Service
CRITICAL SECURITY FIX: CRITICAL-3
Multi-layer MEV protection to prevent front-running
"""

import random
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MEVProtectionService:
    """
    CRITICAL SECURITY FIX: CRITICAL-3
    Multi-layer MEV protection to prevent front-running
    
    Protection layers:
    1. Flashbots/private RPC (if available)
    2. Transaction deadlines (3 blocks = ~36 seconds)
    3. Competitive gas pricing (+20% to beat MEV bots)
    4. Randomized transaction timing (0-500ms delay)
    5. Post-trade sandwich attack detection
    """
    
    def __init__(self, web3_service):
        self.web3 = web3_service
        self.private_rpc_available = self._check_flashbots_support()
        self.block_time = 12  # Kasplex block time in seconds
    
    def _check_flashbots_support(self):
        """Check if private transaction pool is available"""
        # Kasplex may not have Flashbots-style private mempool yet
        # This is a placeholder for future integration
        return False
    
    def apply_mev_protection(self, tx_data, user_address):
        """
        Apply MEV protection to transaction data
        
        Args:
            tx_data: Transaction data dict
            user_address: User's wallet address
        
        Returns:
            Protected transaction data with deadline, optimized gas, randomized timing
        """
        try:
            if self.private_rpc_available:
                return self._send_via_flashbots(tx_data)
            else:
                return self._apply_public_mempool_protection(tx_data, user_address)
        except Exception as e:
            logger.error(f"MEV protection failed: {e}")
            # Return original tx_data if protection fails
            return tx_data
    
    def _send_via_flashbots(self, tx_data):
        """Send via Flashbots/private RPC (future implementation)"""
        # When Kasplex gets private mempool support, implement here
        logger.info("Sending transaction via private mempool")
        return tx_data
    
    def _apply_public_mempool_protection(self, tx_data, user_address):
        """Apply MEV mitigations for public mempool"""
        
        # 1. Add tight deadline (3 blocks = ~36 seconds)
        deadline = self._get_deadline_timestamp(blocks=3)
        
        # If tx_data has params field (for DEX swaps), update deadline
        if 'params' in tx_data:
            tx_data['params']['deadline'] = deadline
        
        # 2. Set competitive gas price (+20% to beat MEV bots)
        competitive_gas = self._get_competitive_gas_price()
        if 'gasPrice' not in tx_data or tx_data['gasPrice'] == 0:
            tx_data['gasPrice'] = competitive_gas
        
        # 3. Randomize timing (reduce predictability)
        delay_ms = random.randint(0, 500)
        time.sleep(delay_ms / 1000)
        
        logger.info(f"MEV protection applied: deadline={deadline}, gas={competitive_gas}, delay={delay_ms}ms")
        
        return tx_data
    
    def _get_deadline_timestamp(self, blocks=3):
        """
        Calculate deadline timestamp (current time + N blocks)
        
        Args:
            blocks: Number of blocks until deadline (default 3 = ~36 seconds)
        
        Returns:
            Unix timestamp for deadline
        """
        deadline_seconds = blocks * self.block_time
        return int(time.time()) + deadline_seconds
    
    def _get_competitive_gas_price(self):
        """Set gas price to beat MEV bots"""
        try:
            base_fee = self.web3.w3.eth.gas_price
            
            # Try to get priority fee (EIP-1559)
            try:
                priority_fee = self.web3.w3.eth.max_priority_fee_per_gas
                # Add 20% priority to beat MEV bots
                competitive_price = int(base_fee + (priority_fee * 1.2))
            except:
                # Fallback: add 20% to base fee
                competitive_price = int(base_fee * 1.2)
            
            return competitive_price
            
        except Exception as e:
            logger.warning(f"Failed to calculate competitive gas: {e}")
            # Fallback to default
            return self.web3.w3.eth.gas_price


class MEVDetector:
    """Post-trade analysis to detect sandwich attacks"""
    
    def __init__(self, web3_service):
        self.web3 = web3_service
    
    def analyze_trade(self, tx_hash, token_address):
        """
        Check if trade was sandwiched
        
        Args:
            tx_hash: Transaction hash to analyze
            token_address: Token contract address
        
        Returns:
            bool: True if sandwich attack detected
        """
        try:
            receipt = self.web3.w3.eth.get_transaction_receipt(tx_hash)
            block_number = receipt.blockNumber
            tx_index = receipt.transactionIndex
            
            # Get all transactions in same block
            block = self.web3.w3.eth.get_block(block_number, full_transactions=True)
            
            # Look for suspicious pattern:
            # [bot buy] → [user trade] → [bot sell]
            sandwich_detected = self._detect_sandwich_pattern(
                block.transactions,
                tx_index,
                token_address
            )
            
            if sandwich_detected:
                logger.warning(f"⚠️ Potential sandwich attack detected on tx {tx_hash}")
            
            return sandwich_detected
            
        except Exception as e:
            logger.error(f"MEV detection failed for {tx_hash}: {e}")
            return False
    
    def _detect_sandwich_pattern(self, transactions, user_tx_index, token_address):
        """
        Detect sandwich attack pattern in block
        
        Pattern: 
        - Transaction before user: Buy same token (front-run)
        - User transaction
        - Transaction after user: Sell same token (back-run)
        
        Args:
            transactions: List of transactions in block
            user_tx_index: Index of user's transaction
            token_address: Token being traded
        
        Returns:
            bool: True if sandwich pattern detected
        """
        # Simplified detection - can be enhanced
        # Would need to decode transaction data to check if it's trading same token
        
        # Check if there's a transaction immediately before and after
        if user_tx_index > 0 and user_tx_index < len(transactions) - 1:
            tx_before = transactions[user_tx_index - 1]
            tx_after = transactions[user_tx_index + 1]
            
            # Same sender before and after suggests possible MEV bot
            if tx_before['from'] == tx_after['from']:
                logger.warning(f"Suspicious: Same address {tx_before['from']} traded before and after user")
                return True
        
        return False
