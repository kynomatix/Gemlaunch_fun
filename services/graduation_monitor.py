"""
Graduation Monitor Service
Monitors token market caps and automatically triggers graduation when they reach the configured threshold (default $50 USD)
"""

import logging
from datetime import datetime, timezone
from services.kas_oracle import oracle
from services.web3_service import get_web3_service
from models import Token, db, PlatformSettings

def check_token_graduation(token):
    """
    Check if a single token should graduate based on market cap
    
    Args:
        token (Token): Token model instance to check
    
    Returns:
        dict: Status dictionary with keys:
            - status (str): 'graduated', 'not_ready', 'already_graduated', or 'error'
            - token_id (int): Token ID
            - token_symbol (str): Token symbol
            - market_cap_usd (float): Current market cap in USD (if available)
            - tx_hash (str): Graduation transaction hash (if graduated)
            - error (str): Error message (if error occurred)
    
    Usage:
        >>> from models import Token
        >>> token = Token.query.filter_by(symbol='MEME').first()
        >>> result = check_token_graduation(token)
        >>> print(f"Status: {result['status']}, Market Cap: ${result.get('market_cap_usd', 0):,.2f}")
    """
    try:
        logging.info(f"Checking graduation for token {token.symbol} (ID: {token.id}, Address: {token.contract_address})")
        
        # Skip if graduation is disabled (legacy V1 tokens)
        if token.graduation_disabled:
            logging.debug(f"Token {token.symbol} has graduation disabled (legacy V1 token)")
            return {
                'status': 'graduation_disabled',
                'token_id': token.id,
                'token_symbol': token.symbol,
                'reason': 'Legacy V1 token - graduation disabled'
            }
        
        # Skip if already graduated
        if token.is_graduated:
            logging.debug(f"Token {token.symbol} already graduated")
            return {
                'status': 'already_graduated',
                'token_id': token.id,
                'token_symbol': token.symbol,
                'market_cap_usd': float(token.current_market_cap) if token.current_market_cap else 0
            }
        
        # Skip if already in graduation process
        if token.graduation_status in ['initiating', 'completing']:
            logging.debug(f"Token {token.symbol} already graduating (status: {token.graduation_status})")
            return {
                'status': 'in_progress',
                'token_id': token.id,
                'token_symbol': token.symbol,
                'graduation_status': token.graduation_status
            }
        
        # Get web3 service
        web3_service = get_web3_service()
        
        # Get pool contract (token contract address IS the pool address)
        pool = web3_service.get_bonding_pool_contract(token.contract_address)
        
        # Get virtualKasReserve from blockchain
        kas_reserve_wei = pool.functions.virtualKasReserve().call()
        
        logging.debug(f"Token {token.symbol} - virtualKasReserve: {kas_reserve_wei} wei ({web3_service.w3.from_wei(kas_reserve_wei, 'ether')} KAS)")
        
        # Check if already graduated on-chain (sync database if needed)
        graduated_onchain = pool.functions.graduated().call()
        if graduated_onchain and not token.is_graduated:
            logging.info(f"✅ Token {token.symbol} already graduated on-chain! Syncing database...")
            token.graduation_status = 'graduated'
            token.is_graduated = True
            if not token.graduation_completed_at:
                token.graduation_completed_at = datetime.now(timezone.utc)
            db.session.commit()
            logging.info(f"✅ {token.symbol} database synced to graduated status")
            return {
                'status': 'already_graduated_synced',
                'token_id': token.id,
                'token_symbol': token.symbol,
                'market_cap_usd': oracle.get_market_cap_usd(kas_reserve_wei)
            }
        
        # Calculate USD market cap using oracle
        market_cap_usd = oracle.get_market_cap_usd(kas_reserve_wei)
        
        # Get dynamic graduation threshold from platform settings
        graduation_threshold_usd = float(PlatformSettings.get_settings().graduation_threshold_usd)
        
        logging.info(f"Token {token.symbol} - Market Cap: ${market_cap_usd:,.2f} USD (Threshold: ${graduation_threshold_usd:,.2f})")
        
        # Check if ready for graduation
        if market_cap_usd >= graduation_threshold_usd:
            logging.info(f"🎓 Token {token.symbol} ready for graduation! Market cap: ${market_cap_usd:,.2f}")
            
            # Use GraduationStateManager to properly handle graduation flow
            from services.graduation_state_manager import GraduationStateManager
            
            # Get oracle wallet from web3_service
            oracle_wallet = web3_service.oracle_account
            
            # Initiate graduation - this will set status to 'initiating' and send tx
            result = GraduationStateManager.initiate_graduation(token, oracle_wallet)
            
            if result.get('success'):
                logging.info(f"✅ Token {token.symbol} graduation initiated! TX: {result.get('tx_hash')}")
                
                return {
                    'status': 'graduation_initiated',
                    'token_id': token.id,
                    'token_symbol': token.symbol,
                    'market_cap_usd': market_cap_usd,
                    'graduation_status': token.graduation_status
                }
            else:
                logging.error(f"❌ Failed to initiate graduation for {token.symbol}")
                return {
                    'status': 'error',
                    'token_id': token.id,
                    'token_symbol': token.symbol,
                    'error': 'Graduation initiation failed'
                }
        else:
            # Not ready yet
            progress_pct = (market_cap_usd / graduation_threshold_usd) * 100
            logging.debug(f"Token {token.symbol} not ready for graduation - Progress: {progress_pct:.1f}%")
            
            # Update market cap in database
            token.current_market_cap = market_cap_usd
            db.session.commit()
            
            return {
                'status': 'not_ready',
                'token_id': token.id,
                'token_symbol': token.symbol,
                'market_cap_usd': market_cap_usd,
                'progress_pct': progress_pct
            }
    
    except Exception as e:
        # CRITICAL: Rollback session to prevent poisoned transaction state
        db.session.rollback()
        
        error_msg = f"Error checking graduation for token {token.symbol} (ID: {token.id}): {str(e)}"
        logging.error(error_msg, exc_info=True)
        
        return {
            'status': 'error',
            'token_id': token.id,
            'token_symbol': token.symbol,
            'error': str(e)
        }


def check_all_graduations():
    """
    Check all active tokens for graduation eligibility
    
    Queries all tokens that:
    - Have not graduated (is_graduated=False)
    - Have been deployed to blockchain (contract_address IS NOT NULL)
    
    Returns:
        dict: Summary dictionary with keys:
            - checked (int): Number of tokens checked
            - graduated (int): Number of tokens that graduated
            - not_ready (int): Number of tokens not ready for graduation
            - already_graduated (int): Number of tokens already graduated (should be 0)
            - errors (int): Number of tokens with errors
            - results (list): List of individual token check results
            - timestamp (datetime): When the check was performed
    
    Usage:
        >>> from services.graduation_monitor import check_all_graduations
        >>> summary = check_all_graduations()
        >>> print(f"Checked: {summary['checked']}, Graduated: {summary['graduated']}, Errors: {summary['errors']}")
    
    TODO: Add rate limiting to prevent overwhelming the RPC node
    """
    try:
        logging.info("Starting graduation check for all active tokens")
        
        # Query non-graduated tokens with contract addresses
        # Exclude tokens with graduation_disabled=True (legacy V1 tokens)
        active_tokens = Token.query.filter_by(
            is_graduated=False,
            deployment_status='deployed',
            graduation_disabled=False  # Skip legacy V1 tokens
        ).filter(
            Token.contract_address.isnot(None)
        ).all()
        
        logging.info(f"Found {len(active_tokens)} active tokens to check")
        
        # Initialize summary counters
        summary = {
            'checked': 0,
            'graduated': 0,
            'not_ready': 0,
            'already_graduated': 0,
            'errors': 0,
            'results': [],
            'timestamp': datetime.now(timezone.utc)
        }
        
        # Check each token
        for token in active_tokens:
            result = check_token_graduation(token)
            summary['results'].append(result)
            summary['checked'] += 1
            
            # Update counters based on status
            if result['status'] == 'graduated':
                summary['graduated'] += 1
            elif result['status'] == 'not_ready':
                summary['not_ready'] += 1
            elif result['status'] == 'already_graduated':
                summary['already_graduated'] += 1
            elif result['status'] == 'error':
                summary['errors'] += 1
        
        # Log summary
        logging.info(
            f"Graduation check complete - "
            f"Checked: {summary['checked']}, "
            f"Graduated: {summary['graduated']}, "
            f"Not Ready: {summary['not_ready']}, "
            f"Errors: {summary['errors']}"
        )
        
        return summary
    
    except Exception as e:
        # CRITICAL: Rollback session to prevent poisoned transaction state
        db.session.rollback()
        
        error_msg = f"Fatal error in check_all_graduations: {str(e)}"
        logging.error(error_msg, exc_info=True)
        
        return {
            'checked': 0,
            'graduated': 0,
            'not_ready': 0,
            'already_graduated': 0,
            'errors': 1,
            'results': [],
            'error': str(e),
            'timestamp': datetime.now(timezone.utc)
        }
