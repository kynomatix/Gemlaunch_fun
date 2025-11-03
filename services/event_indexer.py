"""
Blockchain Event Indexer Service
Listens to blockchain events and stores them in the database
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from web3.exceptions import BlockNotFound
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import db
from models import Token, TradeEvent, AntiBotFeeTracker
from services.web3_service import Web3Service
from services.engagement_calculator import update_engagement_batch
from services.user_stats_updater import update_user_stats_batch
from services.holding_updater import update_holdings_batch
from services.activity_logger import create_activities_batch

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

INDEXER_STATE_FILE = Path("config/indexer_state.json")
BATCH_SIZE = 250  # Configurable batch size for event processing (100-500 recommended)

# Generic ERC20 Transfer event ABI for decoding token transfer logs
ERC20_TRANSFER_ABI = {
    'anonymous': False,
    'inputs': [
        {'indexed': True, 'name': 'from', 'type': 'address'},
        {'indexed': True, 'name': 'to', 'type': 'address'},
        {'indexed': False, 'name': 'value', 'type': 'uint256'}
    ],
    'name': 'Transfer',
    'type': 'event'
}

def _load_airdrop_distributor_address():
    """
    Load AirdropDistributor contract address from deployed_addresses.json
    
    Returns:
        str: AirdropDistributor contract address
    
    Raises:
        FileNotFoundError: If deployed_addresses.json is not found
        KeyError: If AirdropDistributor address is missing from config
        ValueError: If address format is invalid
    """
    config_path = Path("contracts/deployed_addresses.json")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        address = config['contracts']['AirdropDistributor']['address']
        
        if not address or not isinstance(address, str):
            raise ValueError(f"Invalid AirdropDistributor address in config: {address}")
        
        logger.debug(f"Loaded AirdropDistributor address from config: {address}")
        return address
        
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(
            f"Deployed addresses config file not found at {config_path}. "
            "Please ensure contracts/deployed_addresses.json exists."
        )
    except KeyError as e:
        logger.error(f"AirdropDistributor address not found in config: {e}")
        raise KeyError(
            "AirdropDistributor address not found in deployed_addresses.json. "
            f"Expected path: contracts.AirdropDistributor.address. Missing key: {e}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise ValueError(f"Invalid JSON in {config_path}: {e}")

AIRDROP_DISTRIBUTOR_ADDRESS = _load_airdrop_distributor_address()

def get_web3_service():
    """Get or create Web3Service instance"""
    if not hasattr(get_web3_service, '_instance'):
        get_web3_service._instance = Web3Service()
    return get_web3_service._instance


def get_erc20_transfer_decoder(w3, token_address):
    """
    Create a generic ERC20 contract instance for decoding Transfer events
    
    This uses only the Transfer event ABI, making it compatible with any ERC20 token
    regardless of the specific token contract implementation.
    
    Args:
        w3: Web3 instance
        token_address: Address of the ERC20 token contract
    
    Returns:
        Contract instance with Transfer event decoder
    """
    contract = w3.eth.contract(
        address=w3.to_checksum_address(token_address),
        abi=[ERC20_TRANSFER_ABI]
    )
    return contract


def bulk_fetch_blocks(w3, block_numbers):
    """
    Pre-fetch blocks in bulk for all events in a batch
    
    Args:
        w3: Web3 instance
        block_numbers: Set/list of block numbers to fetch
    
    Returns:
        dict: Block number -> block data mapping
    """
    blocks = {}
    unique_blocks = set(block_numbers)
    
    for block_num in unique_blocks:
        try:
            block = w3.eth.get_block(block_num)
            blocks[block_num] = block
        except BlockNotFound:
            logger.warning(f"Block {block_num} not found")
            continue
    
    logger.debug(f"Pre-fetched {len(blocks)} blocks for batch processing")
    return blocks


def filter_existing_tx_hashes(tx_hashes):
    """
    Pre-filter duplicate transactions before batch insert
    
    Args:
        tx_hashes: List of transaction hashes to check
    
    Returns:
        set: Transaction hashes that already exist in database
    """
    if not tx_hashes:
        return set()
    
    existing = db.session.query(TradeEvent.tx_hash)\
        .filter(TradeEvent.tx_hash.in_(tx_hashes))\
        .all()
    
    existing_set = {row[0] for row in existing}
    
    if existing_set:
        logger.debug(f"Filtered out {len(existing_set)} duplicate transactions")
    
    return existing_set


def calculate_holder_counts_batch(token_ids):
    """
    Calculate holder counts for multiple tokens in one query
    
    Args:
        token_ids: List of token IDs to calculate holders for
    
    Returns:
        dict: Token ID -> holder count mapping
    """
    if not token_ids:
        return {}
    
    # Use efficient GROUP BY query instead of per-token COUNT DISTINCT
    from sqlalchemy import func
    
    results = db.session.query(
        TradeEvent.token_id,
        func.count(func.distinct(TradeEvent.user_wallet_address))
    ).filter(
        TradeEvent.token_id.in_(token_ids),
        TradeEvent.trade_type == 'buy'
    ).group_by(TradeEvent.token_id).all()
    
    holder_counts = {token_id: count for token_id, count in results}
    
    logger.debug(f"Calculated holder counts for {len(holder_counts)} tokens in batch")
    return holder_counts


def get_last_indexed_block():
    """Get last indexed block from config file"""
    try:
        if INDEXER_STATE_FILE.exists():
            with open(INDEXER_STATE_FILE, 'r') as f:
                state = json.load(f)
                return state.get('last_indexed_block', 0)
        return 0
    except Exception as e:
        logger.error(f"Error reading last indexed block: {str(e)}")
        return 0


def set_last_indexed_block(block_number):
    """Store last indexed block in config file"""
    try:
        INDEXER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        state = {'last_indexed_block': block_number}
        with open(INDEXER_STATE_FILE, 'w') as f:
            json.dump(state, f)
        
        logger.debug(f"Updated last indexed block to {block_number}")
    except Exception as e:
        logger.error(f"Error saving last indexed block: {str(e)}")


def build_trade_event_from_purchase(event, token, block, w3):
    """Build TradeEvent object from TokensPurchased event (no DB insert)"""
    args = event['args']
    tx_hash = event['transactionHash'].hex()
    block_number = event['blockNumber']
    
    timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
    
    buyer_address = args['buyer'].lower()
    tokens_out = Decimal(str(args['tokensOut']))
    trade_amount = Decimal(str(w3.from_wei(args['tradeAmount'], 'ether')))
    platform_fee = Decimal(str(w3.from_wei(args['platformFee'], 'ether')))
    creator_fee = Decimal(str(w3.from_wei(args['creatorFee'], 'ether')))
    anti_bot_fee = Decimal(str(w3.from_wei(args['antiBotFee'], 'ether')))
    
    total_kas = trade_amount + platform_fee + creator_fee + anti_bot_fee
    
    trade_event = TradeEvent(
        token_id=token.id,
        user_wallet_address=buyer_address,
        trade_type='buy',
        kas_amount=total_kas,
        token_amount=tokens_out,
        platform_fee=platform_fee,
        creator_fee=creator_fee,
        anti_bot_fee=anti_bot_fee,
        tx_hash=tx_hash,
        block_number=block_number,
        timestamp=timestamp
    )
    
    return trade_event, total_kas


def process_tokens_purchased_event(event, token, w3):
    """DEPRECATED: Legacy single-event processor (kept for compatibility)"""
    try:
        block = w3.eth.get_block(event['blockNumber'])
        trade_event, total_kas = build_trade_event_from_purchase(event, token, block, w3)
        
        db.session.add(trade_event)
        db.session.flush()
        
        token.trade_count = (token.trade_count or 0) + 1
        token.trading_volume_24h = (token.trading_volume_24h or 0) + total_kas
        
        unique_holders = db.session.query(TradeEvent.user_wallet_address)\
            .filter(TradeEvent.token_id == token.id)\
            .filter(TradeEvent.trade_type == 'buy')\
            .distinct().count()
        token.holder_count = unique_holders
        
        logger.debug(f"✅ Processed TokensPurchased: {trade_event.token_amount} tokens for {total_kas} KAS")
        
        return trade_event
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower() and 'tx_hash' in str(e).lower():
            logger.debug(f"Skipping duplicate TokensPurchased event")
            db.session.rollback()
            return None
        raise
    except Exception as e:
        logger.error(f"Error processing TokensPurchased event: {str(e)}")
        db.session.rollback()
        raise


def build_trade_event_from_sell(event, token, block, w3):
    """Build TradeEvent object from TokensSold event (no DB insert)"""
    args = event['args']
    tx_hash = event['transactionHash'].hex()
    block_number = event['blockNumber']
    
    timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
    
    seller_address = args['seller'].lower()
    tokens_in = Decimal(str(args['tokensIn']))
    kas_out = Decimal(str(w3.from_wei(args['kasOut'], 'ether')))
    platform_fee = Decimal(str(w3.from_wei(args['platformFee'], 'ether')))
    creator_fee = Decimal(str(w3.from_wei(args['creatorFee'], 'ether')))
    
    trade_event = TradeEvent(
        token_id=token.id,
        user_wallet_address=seller_address,
        trade_type='sell',
        kas_amount=kas_out,
        token_amount=tokens_in,
        platform_fee=platform_fee,
        creator_fee=creator_fee,
        anti_bot_fee=0,
        tx_hash=tx_hash,
        block_number=block_number,
        timestamp=timestamp
    )
    
    return trade_event, kas_out


def build_trade_event_from_airdrop(event, token, block, w3):
    """Build TradeEvent object from Transfer event (airdrop from AirdropDistributor)"""
    args = event['args']
    tx_hash = event['transactionHash'].hex()
    block_number = event['blockNumber']
    
    timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
    
    recipient_address = args['to'].lower()
    token_amount = Decimal(str(args['value']))
    
    trade_event = TradeEvent(
        token_id=token.id,
        user_wallet_address=recipient_address,
        trade_type='airdrop',
        kas_amount=0,  # Airdrops are $0 cost basis
        token_amount=token_amount,
        platform_fee=0,
        creator_fee=0,
        anti_bot_fee=0,
        tx_hash=tx_hash,
        block_number=block_number,
        timestamp=timestamp
    )
    
    return trade_event


def process_tokens_sold_event(event, token, w3):
    """DEPRECATED: Legacy single-event processor (kept for compatibility)"""
    try:
        block = w3.eth.get_block(event['blockNumber'])
        trade_event, kas_out = build_trade_event_from_sell(event, token, block, w3)
        
        db.session.add(trade_event)
        db.session.flush()
        
        token.trade_count = (token.trade_count or 0) + 1
        token.trading_volume_24h = (token.trading_volume_24h or 0) + kas_out
        
        logger.debug(f"✅ Processed TokensSold: {trade_event.token_amount} tokens for {kas_out} KAS")
        
        return trade_event
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower() and 'tx_hash' in str(e).lower():
            logger.debug(f"Skipping duplicate TokensSold event")
            db.session.rollback()
            return None
        raise
    except Exception as e:
        logger.error(f"Error processing TokensSold event: {str(e)}")
        db.session.rollback()
        raise


def process_anti_bot_fee_events(w3, pool_contract, token, from_block, to_block):
    """Process AntiBotFeePaid and AntiBotFeeSplit events together (they're in same tx)"""
    try:
        anti_bot_paid_filter = pool_contract.events.AntiBotFeePaid.create_filter(
            from_block=from_block,
            to_block=to_block
        )
        anti_bot_paid_events = anti_bot_paid_filter.get_all_entries()
        
        for paid_event in anti_bot_paid_events:
            try:
                tx_hash = paid_event['transactionHash'].hex()
                block_number = paid_event['blockNumber']
                
                block = w3.eth.get_block(block_number)
                timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
                
                user_address = paid_event['args']['user'].lower()
                fee_amount = Decimal(str(w3.from_wei(paid_event['args']['feeAmount'], 'ether')))
                elapsed_seconds = paid_event['args']['elapsedSeconds']
                
                trade_event = TradeEvent.query.filter_by(
                    token_id=token.id,
                    tx_hash=tx_hash,
                    user_wallet_address=user_address
                ).first()
                
                if not trade_event:
                    logger.warning(f"No matching TradeEvent found for AntiBotFeePaid (tx: {tx_hash})")
                    continue
                
                split_filter = pool_contract.events.AntiBotFeeSplit.create_filter(
                    from_block=block_number,
                    to_block=block_number
                )
                split_events = [e for e in split_filter.get_all_entries() if e['transactionHash'].hex() == tx_hash]
                
                if split_events:
                    split_event = split_events[0]
                    leaderboard_amount = Decimal(str(w3.from_wei(split_event['args']['leaderboardAmount'], 'ether')))
                    platform_dev_amount = Decimal(str(w3.from_wei(split_event['args']['platformDevAmount'], 'ether')))
                else:
                    leaderboard_amount = fee_amount * Decimal('0.7')
                    platform_dev_amount = fee_amount * Decimal('0.3')
                
                anti_bot_tracker = AntiBotFeeTracker(
                    token_id=token.id,
                    trade_event_id=trade_event.id,
                    total_anti_bot_fee=fee_amount,
                    airdrop_treasury_amount=leaderboard_amount,
                    platform_dev_amount=platform_dev_amount,
                    tx_hash=tx_hash,
                    block_number=block_number,
                    timestamp=timestamp
                )
                
                db.session.add(anti_bot_tracker)
                
                logger.debug(f"✅ Processed AntiBotFee: {fee_amount} KAS (70/30 split) after {elapsed_seconds}s (tx: {tx_hash[:10]}...)")
                
            except IntegrityError as e:
                logger.debug(f"Skipping duplicate AntiBotFee event: {tx_hash}")
                db.session.rollback()
                continue
            except Exception as e:
                logger.error(f"Error processing AntiBotFee event {tx_hash}: {str(e)}")
                db.session.rollback()
                continue
                
    except Exception as e:
        logger.error(f"Error processing anti-bot fee events: {str(e)}")


def process_graduation_initiated_pool_event(event, token, w3):
    """Process GraduationInitiated event from BondingCurvePool
    
    NOTE: This event means graduation has STARTED, not completed.
    Do NOT set is_graduated=True here - that should only happen when
    GraduationCompleted event is emitted from GraduationController.
    """
    try:
        tx_hash = event['transactionHash'].hex()
        block_number = event['blockNumber']
        
        block = w3.eth.get_block(block_number)
        timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
        
        args = event['args']
        kas_liquidity = Decimal(str(w3.from_wei(args['kasLiquidity'], 'ether')))
        token_liquidity = Decimal(str(args['tokenLiquidity']))
        
        # Store liquidity amounts for reference, but do NOT mark as graduated yet
        token.kas_reserve = kas_liquidity
        token.token_reserve = token_liquidity
        
        logger.debug(f"✅ Processed Pool GraduationInitiated: {token.symbol} at block {block_number} (tx: {tx_hash[:10]}...)")
        
    except Exception as e:
        logger.error(f"Error processing Pool GraduationInitiated event: {str(e)}")
        db.session.rollback()
        raise


def process_creator_fees_withdrawn_event(event, token, w3):
    """Process CreatorFeesWithdrawn event"""
    try:
        args = event['args']
        tx_hash = event['transactionHash'].hex()
        block_number = event['blockNumber']
        
        block = w3.eth.get_block(block_number)
        timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
        
        creator_address = args['creator'].lower()
        amount = Decimal(str(w3.from_wei(args['amount'], 'ether')))
        
        trade_event = TradeEvent(
            token_id=token.id,
            user_wallet_address=creator_address,
            trade_type='creator_withdraw',
            kas_amount=amount,
            token_amount=0,
            platform_fee=0,
            creator_fee=0,
            anti_bot_fee=0,
            tx_hash=tx_hash,
            block_number=block_number,
            timestamp=timestamp
        )
        
        db.session.add(trade_event)
        
        token.creator_fees_accumulated = max(0, (token.creator_fees_accumulated or 0) - amount)
        
        logger.debug(f"✅ Processed CreatorFeesWithdrawn: {amount} KAS by {creator_address[:10]}... (tx: {tx_hash[:10]}...)")
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower() and 'tx_hash' in str(e).lower():
            logger.debug(f"Skipping duplicate CreatorFeesWithdrawn event: {tx_hash}")
            db.session.rollback()
            return
        raise
    except Exception as e:
        logger.error(f"Error processing CreatorFeesWithdrawn event: {str(e)}")
        db.session.rollback()
        raise


def process_trade_events_batch(purchase_events, sell_events, token, w3, blocks_cache, airdrop_events=None):
    """
    Process trade events in batch for optimal performance
    
    Args:
        purchase_events: List of TokensPurchased events
        sell_events: List of TokensSold events
        token: Token model instance
        w3: Web3 instance
        blocks_cache: Pre-fetched blocks dict {block_number: block_data}
        airdrop_events: List of Transfer events from AirdropDistributor (optional)
    
    Returns:
        dict: Statistics about processed events
    """
    import time
    batch_start = time.time()
    
    stats = {
        'purchases': 0,
        'sells': 0,
        'airdrops': 0,
        'duplicates': 0,
        'errors': 0,
        'batch_duration': 0
    }
    
    # Step 1: Build all trade event objects (no DB operations yet)
    trade_events = []
    
    # Process purchases
    for event in purchase_events:
        try:
            block_number = event['blockNumber']
            block = blocks_cache.get(block_number)
            if not block:
                logger.warning(f"Block {block_number} not in cache, fetching...")
                block = w3.eth.get_block(block_number)
            
            trade_event, kas_amount = build_trade_event_from_purchase(event, token, block, w3)
            trade_events.append((trade_event, kas_amount))
        except Exception as e:
            logger.error(f"Error building purchase event: {str(e)}")
            stats['errors'] += 1
            continue
    
    # Process sells
    for event in sell_events:
        try:
            block_number = event['blockNumber']
            block = blocks_cache.get(block_number)
            if not block:
                logger.warning(f"Block {block_number} not in cache, fetching...")
                block = w3.eth.get_block(block_number)
            
            trade_event, kas_amount = build_trade_event_from_sell(event, token, block, w3)
            trade_events.append((trade_event, kas_amount))
        except Exception as e:
            logger.error(f"Error building sell event: {str(e)}")
            stats['errors'] += 1
            continue
    
    # Process airdrops (if provided)
    if airdrop_events:
        for event in airdrop_events:
            try:
                block_number = event['blockNumber']
                block = blocks_cache.get(block_number)
                if not block:
                    logger.warning(f"Block {block_number} not in cache, fetching...")
                    block = w3.eth.get_block(block_number)
                
                trade_event = build_trade_event_from_airdrop(event, token, block, w3)
                trade_events.append((trade_event, 0))  # $0 cost for airdrops
            except Exception as e:
                logger.error(f"Error building airdrop event: {str(e)}")
                stats['errors'] += 1
                continue
    
    if not trade_events:
        return stats
    
    # Step 2: Pre-filter duplicates
    tx_hashes = [te[0].tx_hash for te in trade_events]
    existing_hashes = filter_existing_tx_hashes(tx_hashes)
    
    # Filter to only new events (not duplicates)
    new_trade_events_with_amounts = [(te, amt) for te, amt in trade_events if te.tx_hash not in existing_hashes]
    stats['duplicates'] = len(existing_hashes)
    
    if not new_trade_events_with_amounts:
        logger.debug(f"All {len(trade_events)} events were duplicates, skipping insert")
        return stats
    
    # Extract trade events for insertion and calculate metrics from NEW events only
    new_trade_events = [te for te, amt in new_trade_events_with_amounts]
    
    # Step 3: Bulk insert trade events
    try:
        db.session.bulk_save_objects(new_trade_events)
        
        stats['purchases'] = len([e for e in new_trade_events if e.trade_type == 'buy'])
        stats['sells'] = len([e for e in new_trade_events if e.trade_type == 'sell'])
        stats['airdrops'] = len([e for e in new_trade_events if e.trade_type == 'airdrop'])
        
        logger.debug(f"✅ Batch inserted {len(new_trade_events)} trade events ({stats['purchases']} buys, {stats['sells']} sells, {stats['airdrops']} airdrops)")
        
        # Step 3.5: Call side effect services (CRITICAL: update user stats, holdings, activities)
        # User stats updater
        updated_users = update_user_stats_batch(new_trade_events_with_amounts)
        
        # Holding updater
        update_holdings_batch(new_trade_events)
        
        # Activity logger
        create_activities_batch(new_trade_events, token)
        
        # Evaluate achievements for users who traded (auto-award trading achievements)
        if updated_users > 0:
            from services.achievement_service import evaluate_user_achievements
            unique_wallets = set(te.user_wallet_address.lower() for te, _ in new_trade_events_with_amounts)
            for wallet in unique_wallets:
                user = User.query.filter_by(wallet_address=wallet).first()
                if user:
                    try:
                        evaluate_user_achievements(user.id)
                    except Exception as e:
                        logger.error(f"Error evaluating achievements for user {wallet[:10]}...: {str(e)}")
        
        # Step 3.6: Track per-token engagement for PRO tokens
        from services.token_service import TokenService
        if TokenService.is_pro_token(token):
            from models import User, TokenEngagement
            
            for trade_event, kas_amount in new_trade_events_with_amounts:
                # Find user by wallet address
                user = User.query.filter_by(wallet_address=trade_event.user_wallet_address.lower()).first()
                if not user:
                    continue
                
                # Get or create engagement record
                engagement = TokenEngagement.get_or_create(user.id, token.id)
                
                # Check if user is the token creator
                is_creator = (user.id == token.creator_id)
                
                # Update based on trade type
                if trade_event.trade_type == 'buy':
                    engagement.buy_count = (engagement.buy_count or 0) + 1
                    engagement.trades_count = (engagement.trades_count or 0) + 1
                    engagement.total_traded_volume = (engagement.total_traded_volume or 0) + kas_amount
                    
                    # Award token-specific leaderboard points (but NOT to the creator)
                    if not is_creator:
                        engagement.community_points = (engagement.community_points or 0) + 10  # 10 points per buy
                    
                    # Update first acquired timestamp if this is their first purchase
                    if not engagement.first_acquired_at:
                        engagement.first_acquired_at = trade_event.timestamp
                
                elif trade_event.trade_type == 'sell':
                    engagement.sell_count = (engagement.sell_count or 0) + 1
                    engagement.trades_count = (engagement.trades_count or 0) + 1
                    engagement.total_traded_volume = (engagement.total_traded_volume or 0) + kas_amount
                    
                    # Award token-specific leaderboard points (but NOT to the creator)
                    if not is_creator:
                        engagement.community_points = (engagement.community_points or 0) + 5  # 5 points per sell
                
                elif trade_event.trade_type == 'airdrop':
                    # Airdrops: Update first acquired timestamp but don't add to trade count
                    # Airdrops are rewards for engagement, not trades
                    if not engagement.first_acquired_at:
                        engagement.first_acquired_at = trade_event.timestamp
                
                engagement.last_activity_at = trade_event.timestamp
            
            logger.debug(f"✅ Updated engagement for {len(new_trade_events)} trades in PRO token {token.symbol}")
        
    except IntegrityError as e:
        logger.error(f"Unexpected IntegrityError in batch insert: {str(e)}")
        db.session.rollback()
        stats['errors'] += 1
        return stats
    
    # Step 4: Update token metrics using ONLY new events (post-duplicate filter)
    new_trade_count = len(new_trade_events)
    new_trading_volume = sum(amt for te, amt in new_trade_events_with_amounts)
    
    token.trade_count = (token.trade_count or 0) + new_trade_count
    token.trading_volume_24h = (token.trading_volume_24h or 0) + new_trading_volume
    
    # Step 5: Calculate holder count (single query per token, not per event)
    holder_counts = calculate_holder_counts_batch([token.id])
    if token.id in holder_counts:
        token.holder_count = holder_counts[token.id]
    
    # Step 6: Sync reserves from blockchain (CRITICAL FIX)
    # After processing trades OR if reserves are stale, read actual blockchain reserves
    should_sync = (new_trade_count > 0) or (not token.kas_reserve or token.kas_reserve == 0)
    
    if should_sync and not token.is_graduated:
        try:
            web3_service = get_web3_service()
            pool_address = token.liquidity_pool_address or token.contract_address
            pool_contract = web3_service.get_bonding_pool_contract(pool_address)
            
            # Read current reserves from blockchain
            kas_reserve_wei = pool_contract.functions.virtualKasReserve().call()
            token_reserve_wei = pool_contract.functions.virtualTokenReserve().call()
            
            kas_reserve = float(w3.from_wei(kas_reserve_wei, 'ether'))
            token_reserve = float(token_reserve_wei) / 1e18
            
            # Calculate price
            new_price = kas_reserve / token_reserve if token_reserve > 0 else 0
            
            # Update token with blockchain values
            token.update_market_data(new_price, kas_reserve, token_reserve_wei)
            
            logger.info(f"✅ Synced reserves for {token.symbol}: {kas_reserve:.2f} KAS, price={new_price:.8f} KAS")
        except Exception as e:
            logger.error(f"Error syncing reserves for {token.symbol}: {str(e)}")
    
    stats['batch_duration'] = time.time() - batch_start
    logger.debug(f"📊 Batch metrics: {len(new_trade_events)} events in {stats['batch_duration']:.2f}s ({len(new_trade_events)/stats['batch_duration']:.1f} events/sec)")
    
    return stats


def process_bonding_pool_events(pool_address, from_block, to_block):
    """Process all BondingCurvePool events for a token with optimized batch processing"""
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        # Use case-insensitive comparison (ILIKE in PostgreSQL)
        from sqlalchemy import func
        # Look up token by liquidity_pool_address (BondingCurvePool) since that's where trade events are emitted
        token = Token.query.filter(
            db.or_(
                func.lower(Token.liquidity_pool_address) == pool_address.lower(),
                func.lower(Token.contract_address) == pool_address.lower()  # Fallback for old data
            )
        ).first()
        if not token:
            logger.warning(f"Token not found for pool address: {pool_address}")
            return {'success': False, 'error': 'Token not found'}
        
        pool_contract = web3_service.get_bonding_pool_contract(pool_address)
        
        stats = {
            'token_symbol': token.symbol,
            'purchases': 0,
            'sells': 0,
            'anti_bot_fees': 0,
            'graduations': 0,
            'withdrawals': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        # Fetch all events for the block range
        purchase_events = []
        sell_events = []
        airdrop_events = []
        
        try:
            purchase_filter = pool_contract.events.TokensPurchased.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            purchase_events = purchase_filter.get_all_entries()
            logger.debug(f"Found {len(purchase_events)} purchase events for {token.symbol}")
        except Exception as e:
            logger.error(f"Error fetching TokensPurchased events: {str(e)}")
        
        try:
            sell_filter = pool_contract.events.TokensSold.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            sell_events = sell_filter.get_all_entries()
            logger.debug(f"Found {len(sell_events)} sell events for {token.symbol}")
        except Exception as e:
            logger.error(f"Error fetching TokensSold events: {str(e)}")
        
        # Fetch AirdropDistributed events and extract Transfer events from those transactions
        try:
            # Get AirdropDistributor contract from web3_service
            w3_service = get_web3_service()
            airdrop_distributor_contract = w3_service.contracts['AirdropDistributor']
            
            # Listen for AirdropDistributed events for this token
            airdrop_distributed_filter = airdrop_distributor_contract.events.AirdropDistributed.create_filter(
                from_block=from_block,
                to_block=to_block,
                argument_filters={'token': w3.to_checksum_address(token.contract_address)}
            )
            airdrop_distributed_events = airdrop_distributed_filter.get_all_entries()
            
            if airdrop_distributed_events:
                logger.debug(f"Found {len(airdrop_distributed_events)} AirdropDistributed events for {token.symbol}")
                
                # Create generic ERC20 contract instance for decoding Transfer events
                erc20_contract = get_erc20_transfer_decoder(w3, token.contract_address)
                
                # For each AirdropDistributed event, extract Transfer events from the transaction
                for airdrop_event in airdrop_distributed_events:
                    tx_hash = airdrop_event['transactionHash']
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    
                    # Parse Transfer events from this transaction using generic ERC20 ABI
                    for log in receipt['logs']:
                        # Check if this is a Transfer event from the token contract
                        if log['address'].lower() == token.contract_address.lower():
                            try:
                                # Decode Transfer event using generic ERC20 ABI
                                transfer_event = erc20_contract.events.Transfer().process_log(log)
                                airdrop_events.append(transfer_event)
                            except Exception:
                                # Not a Transfer event or failed to decode - skip
                                pass
                
                logger.debug(f"Extracted {len(airdrop_events)} Transfer events from {len(airdrop_distributed_events)} airdrops for {token.symbol}")
        except Exception as e:
            logger.error(f"Error fetching AirdropDistributed events: {str(e)}")
        
        # Process trade events in optimized batches
        if purchase_events or sell_events or airdrop_events:
            # Pre-fetch all blocks needed for this batch
            block_numbers = set()
            for event in purchase_events + sell_events + airdrop_events:
                block_numbers.add(event['blockNumber'])
            
            blocks_cache = bulk_fetch_blocks(w3, block_numbers)
            
            # Process in batch
            batch_stats = process_trade_events_batch(
                purchase_events, 
                sell_events, 
                token, 
                w3, 
                blocks_cache,
                airdrop_events
            )
            
            # Merge batch stats into overall stats
            stats['purchases'] = batch_stats['purchases']
            stats['sells'] = batch_stats['sells']
            stats['airdrops'] = batch_stats.get('airdrops', 0)
            stats['duplicates'] = batch_stats.get('duplicates', 0)
            stats['errors'] += batch_stats.get('errors', 0)
        
        # Process anti-bot fee events (not batched yet - less frequent)
        try:
            process_anti_bot_fee_events(w3, pool_contract, token, from_block, to_block)
        except Exception as e:
            logger.error(f"Error processing anti-bot fee events: {str(e)}")
        
        try:
            graduation_filter = pool_contract.events.GraduationInitiated.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            graduation_events = graduation_filter.get_all_entries()
            
            for event in graduation_events:
                try:
                    process_graduation_initiated_pool_event(event, token, w3)
                    stats['graduations'] += 1
                except Exception as e:
                    logger.error(f"Error processing graduation event: {str(e)}")
                    stats['errors'] += 1
                    continue
        except Exception as e:
            logger.error(f"Error fetching GraduationInitiated events: {str(e)}")
        
        try:
            withdraw_filter = pool_contract.events.CreatorFeesWithdrawn.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            withdraw_events = withdraw_filter.get_all_entries()
            
            for event in withdraw_events:
                try:
                    process_creator_fees_withdrawn_event(event, token, w3)
                    stats['withdrawals'] += 1
                except Exception as e:
                    logger.error(f"Error processing withdrawal event: {str(e)}")
                    stats['errors'] += 1
                    continue
        except Exception as e:
            logger.error(f"Error fetching CreatorFeesWithdrawn events: {str(e)}")
        
        # Sync reserves from blockchain if token is not graduated and reserves are stale
        if not token.is_graduated and (not token.kas_reserve or token.kas_reserve == 0):
            try:
                # Read current reserves from blockchain
                kas_reserve_wei = pool_contract.functions.virtualKasReserve().call()
                token_reserve_wei = pool_contract.functions.virtualTokenReserve().call()
                
                kas_reserve = float(w3.from_wei(kas_reserve_wei, 'ether'))
                token_reserve = float(token_reserve_wei) / 1e18
                
                # Calculate price
                new_price = kas_reserve / token_reserve if token_reserve > 0 else 0
                
                # Update token with blockchain values
                token.update_market_data(new_price, kas_reserve, token_reserve_wei)
                
                logger.info(f"✅ Synced reserves for {token.symbol}: {kas_reserve:.2f} KAS, price={new_price:.8f} KAS")
            except Exception as e:
                logger.error(f"Error syncing reserves for {token.symbol}: {str(e)}")
        
        db.session.commit()
        
        return {'success': True, 'stats': stats}
        
    except Exception as e:
        logger.error(f"Error processing bonding pool events for {pool_address}: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def build_trade_event_from_dex_swap(event, token, block, w3, trader_address):
    """
    Build TradeEvent object from Uniswap V3 Swap event (no DB insert)
    
    Args:
        event: Swap event from Uniswap V3 pool
        token: Token model instance
        block: Block data
        w3: Web3 instance
        trader_address: Wallet address of trader (from tx.from)
    
    Returns:
        tuple: (TradeEvent, kas_amount)
    """
    args = event['args']
    tx_hash = event['transactionHash'].hex()
    block_number = event['blockNumber']
    
    timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
    
    # Determine trade direction from amount0/amount1
    # Token is token1 (token address), WKAS is token0 (lower address)
    # If amount1 < 0 (tokens out), user is buying
    # If amount1 > 0 (tokens in), user is selling
    amount1 = args['amount1']  # Token amount in wei (negative = out, positive = in)
    amount0 = args['amount0']  # WKAS amount in wei (negative = out, positive = in)
    
    # CRITICAL: Store token amounts in WEI (raw format) to match bonding curve trades
    # The display layer will convert to human-readable format using token decimals
    if amount1 < 0:  # Tokens out = Buy
        trade_type = 'dex_buy'
        token_amount = Decimal(str(abs(amount1)))  # Store in wei (raw format)
        kas_amount = Decimal(str(w3.from_wei(abs(amount0), 'ether')))  # WKAS in KAS
    else:  # Tokens in = Sell
        trade_type = 'dex_sell'
        token_amount = Decimal(str(abs(amount1)))  # Store in wei (raw format)
        kas_amount = Decimal(str(w3.from_wei(abs(amount0), 'ether')))  # WKAS out in KAS
    
    trade_event = TradeEvent(
        token_id=token.id,
        user_wallet_address=trader_address.lower(),
        trade_type=trade_type,
        kas_amount=kas_amount,
        token_amount=token_amount,
        platform_fee=0,  # No platform fees on DEX
        creator_fee=0,   # No creator fees on DEX (LP fees go to LPs)
        anti_bot_fee=0,
        tx_hash=tx_hash,
        block_number=block_number,
        timestamp=timestamp,
        is_dex_trade=True  # Flag as DEX trade for filtering
    )
    
    return trade_event, kas_amount


def process_dex_swap_events_batch(swap_events, token, w3, blocks_cache):
    """
    Process DEX Swap events in batch for optimal performance
    
    Args:
        swap_events: List of Swap events from Uniswap V3 pool
        token: Token model instance
        w3: Web3 instance
        blocks_cache: Pre-fetched blocks dict {block_number: block_data}
    
    Returns:
        dict: Statistics about processed events
    """
    import time
    batch_start = time.time()
    
    stats = {
        'dex_buys': 0,
        'dex_sells': 0,
        'duplicates': 0,
        'errors': 0,
        'batch_duration': 0
    }
    
    if not swap_events:
        return stats
    
    # Step 1: Build all trade event objects (with wallet attribution from tx.from)
    trade_events = []
    
    for event in swap_events:
        try:
            block_number = event['blockNumber']
            block = blocks_cache.get(block_number)
            if not block:
                logger.warning(f"Block {block_number} not in cache, fetching...")
                block = w3.eth.get_block(block_number)
            
            # CRITICAL: Get trader address from tx.from (not event.args.sender!)
            # This is the actual wallet that initiated the swap
            tx_hash = event['transactionHash'].hex()
            tx = w3.eth.get_transaction(tx_hash)
            trader_address = tx['from']
            
            trade_event, kas_amount = build_trade_event_from_dex_swap(
                event, token, block, w3, trader_address
            )
            trade_events.append((trade_event, kas_amount))
        except Exception as e:
            logger.error(f"Error building DEX swap event: {str(e)}")
            stats['errors'] += 1
            continue
    
    if not trade_events:
        return stats
    
    # Step 2: Pre-filter duplicates
    tx_hashes = [te[0].tx_hash for te in trade_events]
    existing_hashes = filter_existing_tx_hashes(tx_hashes)
    
    # Filter to only new events
    new_trade_events_with_amounts = [(te, amt) for te, amt in trade_events if te.tx_hash not in existing_hashes]
    stats['duplicates'] = len(existing_hashes)
    
    if not new_trade_events_with_amounts:
        logger.debug(f"All {len(trade_events)} DEX swap events were duplicates, skipping insert")
        return stats
    
    # Extract trade events for insertion
    new_trade_events = [te for te, amt in new_trade_events_with_amounts]
    
    # Step 3: Bulk insert trade events
    try:
        db.session.bulk_save_objects(new_trade_events)
        
        stats['dex_buys'] = len([e for e in new_trade_events if e.trade_type == 'dex_buy'])
        stats['dex_sells'] = len([e for e in new_trade_events if e.trade_type == 'dex_sell'])
        
        logger.debug(f"✅ Batch inserted {len(new_trade_events)} DEX swap events ({stats['dex_buys']} buys, {stats['dex_sells']} sells)")
        
        # Step 4: Call side effect services
        # Engagement calculator
        update_engagement_batch(new_trade_events_with_amounts, token)
        
        # User stats updater
        updated_users = update_user_stats_batch(new_trade_events_with_amounts)
        
        # Holding updater
        update_holdings_batch(new_trade_events)
        
        # Activity logger
        create_activities_batch(new_trade_events, token)
        
        # Evaluate achievements for users who traded (auto-award trading achievements)
        if updated_users > 0:
            from services.achievement_service import evaluate_user_achievements
            from models import User
            unique_wallets = set(te.user_wallet_address.lower() for te, _ in new_trade_events_with_amounts)
            for wallet in unique_wallets:
                user = User.query.filter_by(wallet_address=wallet).first()
                if user:
                    try:
                        evaluate_user_achievements(user.id)
                    except Exception as e:
                        logger.error(f"Error evaluating achievements for user {wallet[:10]}...: {str(e)}")
        
    except IntegrityError as e:
        logger.error(f"Unexpected IntegrityError in DEX batch insert: {str(e)}")
        db.session.rollback()
        stats['errors'] += 1
        return stats
    
    # Step 5: Update token metrics using ONLY new events
    new_trade_count = len(new_trade_events)
    new_trading_volume = sum(amt for te, amt in new_trade_events_with_amounts)
    
    token.trade_count = (token.trade_count or 0) + new_trade_count
    token.trading_volume_24h = (token.trading_volume_24h or 0) + new_trading_volume
    
    # Step 6: Calculate holder count (single query per token)
    holder_counts = calculate_holder_counts_batch([token.id])
    if token.id in holder_counts:
        token.holder_count = holder_counts[token.id]
    
    stats['batch_duration'] = time.time() - batch_start
    logger.debug(f"📊 DEX batch metrics: {len(new_trade_events)} events in {stats['batch_duration']:.2f}s ({len(new_trade_events)/stats['batch_duration']:.1f} events/sec)")
    
    return stats


def process_dex_pool_events(pool_address, from_block, to_block):
    """
    Process all Uniswap V3 pool Swap events for a graduated token
    
    Args:
        pool_address: Address of the Uniswap V3 pool (from token.dex_pool_address)
        from_block: Starting block number
        to_block: Ending block number
    
    Returns:
        dict: Processing results with success status and stats
    """
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        # Look up token by dex_pool_address
        from sqlalchemy import func
        token = Token.query.filter(
            func.lower(Token.dex_pool_address) == pool_address.lower()
        ).first()
        
        if not token:
            logger.warning(f"Token not found for DEX pool address: {pool_address}")
            return {'success': False, 'error': 'Token not found'}
        
        # Load Uniswap V3 Pool contract
        pool_contract = web3_service.get_uniswap_v3_pool_contract(pool_address)
        
        stats = {
            'token_symbol': token.symbol,
            'dex_buys': 0,
            'dex_sells': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        # Fetch Swap events
        swap_events = []
        try:
            swap_filter = pool_contract.events.Swap.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            swap_events = swap_filter.get_all_entries()
            logger.debug(f"Found {len(swap_events)} DEX swap events for {token.symbol}")
        except Exception as e:
            logger.error(f"Error fetching Swap events: {str(e)}")
        
        # Process swap events in optimized batch
        if swap_events:
            # Pre-fetch all blocks needed for this batch
            block_numbers = set()
            for event in swap_events:
                block_numbers.add(event['blockNumber'])
            
            blocks_cache = bulk_fetch_blocks(w3, block_numbers)
            
            # Process in batch
            batch_stats = process_dex_swap_events_batch(
                swap_events,
                token,
                w3,
                blocks_cache
            )
            
            # Merge batch stats into overall stats
            stats['dex_buys'] = batch_stats['dex_buys']
            stats['dex_sells'] = batch_stats['dex_sells']
            stats['duplicates'] = batch_stats.get('duplicates', 0)
            stats['errors'] += batch_stats.get('errors', 0)
        
        db.session.commit()
        
        return {'success': True, 'stats': stats}
        
    except Exception as e:
        logger.error(f"Error processing DEX pool events for {pool_address}: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def process_token_created_events(from_block, to_block):
    """Process TokenCreated events from TokenFactory to update real contract addresses"""
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        token_factory = web3_service.contracts['TokenFactory']
        
        stats = {
            'tokens_deployed': 0,
            'vesting_updated': 0,
            'errors': 0
        }
        
        # Get TokenCreated events
        token_created_filter = token_factory.events.TokenCreated.create_filter(
            from_block=from_block,
            to_block=to_block
        )
        
        events = token_created_filter.get_all_entries()
        logger.debug(f"Found {len(events)} TokenCreated events")
        
        for event in events:
            try:
                args = event['args']
                token_address = args['tokenAddress'].lower()
                pool_address = args['poolAddress'].lower()
                creator = args['creator'].lower()
                name = args['name']
                symbol = args['symbol']
                tx_hash = event['transactionHash'].hex()
                block_number = event['blockNumber']
                timestamp = args['timestamp']
                
                # Find token by creator + symbol (more reliable than mock address)
                token = Token.query.filter_by(symbol=symbol).filter(
                    Token.creator.has(wallet_address=creator)
                ).first()
                
                if token:
                    # Update with real pool/contract address
                    # In BondingCurvePool design, the pool IS the ERC20 token (inherits from ERC20)
                    # tokenAddress and poolAddress from the event are the same contract
                    token.contract_address = pool_address  # The pool contract (which is also the ERC20 token)
                    token.liquidity_pool_address = pool_address  # Same address, stored for event indexing
                    token.deployment_tx = tx_hash
                    token.deployment_status = 'deployed'
                    token.deployment_block_number = block_number
                    
                    db.session.flush()
                    stats['tokens_deployed'] += 1
                    
                    logger.debug(f"✅ Updated Token {symbol} with real address: {token_address[:10]}... (tx: {tx_hash[:10]}...)")
                else:
                    logger.warning(f"Token not found for TokenCreated event: {symbol} by {creator[:10]}...")
                    
            except Exception as e:
                logger.error(f"Error processing TokenCreated event: {str(e)}")
                db.session.rollback()
                stats['errors'] += 1
                continue
        
        # Get VestingDeployed events (emitted for PRO tokens with vesting)
        try:
            vesting_deployed_filter = token_factory.events.VestingDeployed.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            
            vesting_events = vesting_deployed_filter.get_all_entries()
            logger.debug(f"Found {len(vesting_events)} VestingDeployed events")
            
            for event in vesting_events:
                try:
                    args = event['args']
                    token_address = args['token'].lower()
                    airdrop_vesting = args['airdropVesting'].lower()
                    marketing_vesting = args['marketingVesting'].lower()
                    team_vesting = args['teamVesting'].lower()
                    
                    # Find token by contract address
                    token = Token.query.filter_by(contract_address=token_address).first()
                    
                    if token:
                        # Update vesting contract addresses (address(0) means 0% allocation)
                        if airdrop_vesting != '0x0000000000000000000000000000000000000000':
                            token.airdrop_vesting_address = airdrop_vesting
                        if marketing_vesting != '0x0000000000000000000000000000000000000000':
                            token.marketing_vesting_address = marketing_vesting
                        if team_vesting != '0x0000000000000000000000000000000000000000':
                            token.team_vesting_address = team_vesting
                        
                        db.session.flush()
                        stats['vesting_updated'] += 1
                        
                        logger.debug(f"✅ Updated vesting addresses for {token.symbol}: airdrop={airdrop_vesting[:10]}..., marketing={marketing_vesting[:10]}..., team={team_vesting[:10]}...")
                    else:
                        logger.warning(f"Token not found for VestingDeployed event: {token_address}")
                        
                except Exception as e:
                    logger.error(f"Error processing VestingDeployed event: {str(e)}")
                    stats['errors'] += 1
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching VestingDeployed events: {str(e)}")
        
        db.session.commit()
        logger.debug(f"Processed {stats['tokens_deployed']} TokenCreated and {stats['vesting_updated']} VestingDeployed events")
        
        return stats
        
    except Exception as e:
        logger.error(f"Fatal error processing TokenCreated events: {str(e)}")
        db.session.rollback()
        return {'tokens_deployed': 0, 'vesting_updated': 0, 'errors': 1}


def process_graduation_events(from_block, to_block):
    """Process GraduationController events"""
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        graduation_contract = web3_service.contracts['GraduationController']
        
        stats = {
            'initiations': 0,
            'completions': 0,
            'failures': 0,
            'errors': 0
        }
        
        try:
            initiation_filter = graduation_contract.events.GraduationInitiated.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            initiation_events = initiation_filter.get_all_entries()
            
            for event in initiation_events:
                try:
                    args = event['args']
                    token_address = args['tokenAddress'].lower()
                    tx_hash = event['transactionHash'].hex()
                    block_number = event['blockNumber']
                    
                    block = w3.eth.get_block(block_number)
                    timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
                    
                    token = Token.query.filter_by(contract_address=token_address).first()
                    if token:
                        token.is_graduated = True
                        token.graduated_at = timestamp
                        token.graduation_tx = tx_hash
                        
                        kas_liquidity = Decimal(str(w3.from_wei(args['kasLiquidity'], 'ether')))
                        token_liquidity = Decimal(str(args['tokenLiquidity']))
                        token.kas_reserve = kas_liquidity
                        token.token_reserve = token_liquidity
                        
                        stats['initiations'] += 1
                        logger.debug(f"✅ Processed GC GraduationInitiated: {token.symbol} (tx: {tx_hash[:10]}...)")
                    else:
                        logger.warning(f"Token not found for graduation initiation: {token_address}")
                        
                except Exception as e:
                    logger.error(f"Error processing GraduationInitiated event: {str(e)}")
                    stats['errors'] += 1
                    db.session.rollback()
                    continue
        except Exception as e:
            logger.error(f"Error fetching GraduationInitiated events: {str(e)}")
        
        try:
            completion_filter = graduation_contract.events.GraduationCompleted.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            completion_events = completion_filter.get_all_entries()
            
            for event in completion_events:
                try:
                    args = event['args']
                    token_address = args['tokenAddress'].lower()
                    tx_hash = event['transactionHash'].hex()
                    
                    token = Token.query.filter_by(contract_address=token_address).first()
                    if token:
                        token.nft_position_id = args['liquidityPositionId']
                        
                        stats['completions'] += 1
                        logger.debug(f"✅ Processed GraduationCompleted: {token.symbol} NFT #{args['liquidityPositionId']} (tx: {tx_hash[:10]}...)")
                    else:
                        logger.warning(f"Token not found for graduation completion: {token_address}")
                        
                except Exception as e:
                    logger.error(f"Error processing GraduationCompleted event: {str(e)}")
                    stats['errors'] += 1
                    db.session.rollback()
                    continue
        except Exception as e:
            logger.error(f"Error fetching GraduationCompleted events: {str(e)}")
        
        try:
            failure_filter = graduation_contract.events.GraduationFailed.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            failure_events = failure_filter.get_all_entries()
            
            for event in failure_events:
                try:
                    args = event['args']
                    token_address = args['tokenAddress'].lower()
                    reason = args['reason']
                    tx_hash = event['transactionHash'].hex()
                    
                    stats['failures'] += 1
                    logger.warning(f"⚠️ GraduationFailed: {token_address[:10]}... - Reason: {reason} (tx: {tx_hash[:10]}...)")
                    
                except Exception as e:
                    logger.error(f"Error processing GraduationFailed event: {str(e)}")
                    stats['errors'] += 1
                    continue
        except Exception as e:
            logger.error(f"Error fetching GraduationFailed events: {str(e)}")
        
        db.session.commit()
        
        return {'success': True, 'stats': stats}
        
    except Exception as e:
        logger.error(f"Error processing graduation events: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def index_transaction_immediately(tx_hash):
    """
    Index events from a specific transaction immediately (for real-time updates)
    
    Args:
        tx_hash: Transaction hash to index
    
    Returns:
        dict: Indexing result with success status
    """
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        # Get transaction receipt
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if not receipt:
            return {'success': False, 'error': 'Transaction not found'}
        
        block_number = receipt['blockNumber']
        
        # Find the token by contract address from logs
        token_address = None
        for log in receipt['logs']:
            # The first log's address is usually the pool/token contract
            if log['address']:
                token_address = log['address'].lower()
                break
        
        if not token_address:
            return {'success': False, 'error': 'Could not find token address'}
        
        # Find token in database
        token = Token.query.filter(
            db.func.lower(Token.contract_address) == token_address
        ).first()
        
        if not token:
            logger.debug(f"Token not found for address {token_address}")
            return {'success': False, 'error': 'Token not found'}
        
        # Process events from this specific block and token
        # Use liquidity_pool_address (BondingCurvePool) which emits trade events
        pool_address = token.liquidity_pool_address or token.contract_address
        result = process_bonding_pool_events(
            pool_address,
            block_number,
            block_number
        )
        
        if result.get('success'):
            logger.info(f"✅ Immediately indexed transaction {tx_hash[:10]}... - {result.get('buy_count', 0)} buys, {result.get('sell_count', 0)} sells")
            return {'success': True, 'result': result}
        else:
            return {'success': False, 'error': result.get('error', 'Unknown error')}
            
    except Exception as e:
        logger.error(f"Error immediately indexing transaction {tx_hash}: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def process_single_token(token_id, from_block, to_block):
    """
    Worker function to process a single token's events in parallel
    Thread-safe: Creates its own Flask application context and database session
    
    Args:
        token_id: Token database ID
        from_block: Starting block
        to_block: Ending block
    
    Returns:
        dict: Processing results with stats
    """
    from app import app  # Import app for context
    
    result = {
        'token_id': token_id,
        'success': True,
        'trades': 0,
        'graduations': 0,
        'errors': 0
    }
    
    # Create Flask application context for this thread
    with app.app_context():
        try:
            # Fetch token in this thread's context
            token = Token.query.get(token_id)
            if not token:
                result['success'] = False
                result['errors'] = 1
                return result
            
            # STEP 2A: Process bonding curve events (pre-graduation or non-graduated)
            if token.graduation_status in (None, 'active', 'initiating', 'completing'):
                pool_address = token.liquidity_pool_address or token.contract_address
                bc_result = process_bonding_pool_events(
                    pool_address,
                    from_block,
                    to_block
                )
                
                if bc_result.get('success'):
                    stats = bc_result.get('stats', {})
                    result['trades'] += stats.get('purchases', 0) + stats.get('sells', 0)
                    result['graduations'] += stats.get('graduations', 0)
                    result['errors'] += stats.get('errors', 0)
                    logger.debug(f"Token {token.symbol}: {stats.get('purchases', 0)} buys, {stats.get('sells', 0)} sells")
                else:
                    logger.error(f"Failed to process bonding curve events for {token.symbol}: {bc_result.get('error')}")
                    result['errors'] += 1
            
            # STEP 2B: Process DEX events (graduated tokens only)
            elif token.graduation_status == 'graduated' and token.dex_pool_address:
                dex_result = process_dex_pool_events(
                    token.dex_pool_address,
                    from_block,
                    to_block
                )
                
                if dex_result.get('success'):
                    stats = dex_result.get('stats', {})
                    result['trades'] += stats.get('dex_buys', 0) + stats.get('dex_sells', 0)
                    result['errors'] += stats.get('errors', 0)
                    logger.debug(f"DEX Token {token.symbol}: {stats.get('dex_buys', 0)} DEX buys, {stats.get('dex_sells', 0)} DEX sells")
                else:
                    logger.error(f"Failed to process DEX events for {token.symbol}: {dex_result.get('error')}")
                    result['errors'] += 1
                    
        except Exception as e:
            logger.error(f"Error processing token ID {token_id}: {str(e)}")
            result['success'] = False
            result['errors'] += 1
    
    return result


def index_all_events(from_block=None, to_block='latest', max_blocks_per_run=2000):
    """
    Index all events from all contracts
    
    Args:
        from_block: Starting block number (defaults to last indexed block + 1)
        to_block: Ending block number (defaults to 'latest')
        max_blocks_per_run: Maximum blocks to process in one run (default: 2000)
    
    Returns:
        dict: Summary of indexing results
    """
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        if from_block is None:
            last_indexed = get_last_indexed_block()
            from_block = last_indexed + 1 if last_indexed > 0 else 0
        
        if to_block == 'latest':
            to_block = w3.eth.block_number
        
        # Calculate blocks behind and chunk if necessary
        blocks_behind = to_block - from_block
        
        # If we're behind by more than max_blocks_per_run, chunk it
        if blocks_behind > max_blocks_per_run:
            original_to_block = to_block
            to_block = from_block + max_blocks_per_run
            logger.warning(f"⚠️ Event indexer {blocks_behind:,} blocks behind")
            logger.warning(f"📦 Chunking: Processing blocks {from_block:,} to {to_block:,} ({max_blocks_per_run:,} blocks)")
            logger.warning(f"   Remaining: {original_to_block - to_block:,} blocks will be processed in future runs")
        elif blocks_behind > 100:  # ~15 minutes at 6 sec blocks (Kasplex)
            logger.warning(f"⚠️ Event indexer {blocks_behind} blocks behind")
        
        logger.info(f"🔍 Indexing events from block {from_block:,} to {to_block:,} ({blocks_behind if blocks_behind <= max_blocks_per_run else max_blocks_per_run} blocks)")
        
        if from_block > to_block:
            logger.info("No new blocks to index")
            return {
                'success': True,
                'from_block': from_block,
                'to_block': to_block,
                'events_indexed': 0,
                'message': 'No new blocks to index'
            }
        
        summary = {
            'success': True,
            'from_block': from_block,
            'to_block': to_block,
            'events_indexed': 0,
            'trades': 0,
            'graduations': 0,
            'errors': 0,
            'tokens_processed': 0,
            'tokens_deployed': 0
        }
        
        # STEP 1: Process TokenCreated events to update real contract addresses
        logger.info("📝 Step 1: Processing TokenCreated events from TokenFactory")
        token_created_stats = process_token_created_events(from_block, to_block)
        summary['tokens_deployed'] = token_created_stats.get('tokens_deployed', 0)
        summary['errors'] += token_created_stats.get('errors', 0)
        
        # STEP 2: Query deployed tokens (with periodic full scans to catch reactivated tokens)
        # Performance optimization: Index active tokens most of the time, full scan periodically
        from datetime import timedelta
        
        # Check if we should do a full scan (every 10 cycles = ~5 min)
        # This catches tokens that went dormant and then reactivated
        if not hasattr(index_all_events, '_cycle_counter'):
            index_all_events._cycle_counter = 0
        index_all_events._cycle_counter += 1
        
        do_full_scan = (index_all_events._cycle_counter % 10 == 0)
        
        if do_full_scan:
            # FULL SCAN: Index all deployed tokens (catches reactivated tokens)
            deployed_tokens = Token.query.filter(
                Token.contract_address.isnot(None),
                Token.deployment_status == 'deployed'
            ).all()
            logger.info(f"📊 Processing {len(deployed_tokens)} deployed tokens (FULL SCAN cycle #{index_all_events._cycle_counter})")
        else:
            # FAST SCAN: Index only recently active tokens
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            
            # Get tokens with recent trades OR newly deployed OR graduated with DEX pool OR PRO tokens (can receive airdrops)
            deployed_tokens = Token.query.filter(
                Token.contract_address.isnot(None),
                Token.deployment_status == 'deployed'
            ).join(
                TradeEvent,
                TradeEvent.token_id == Token.id,
                isouter=True  # LEFT JOIN to include tokens with no trades yet
            ).filter(
                # Include if: has recent trades OR deployed recently OR no trades yet OR graduated with DEX pool OR PRO token
                db.or_(
                    TradeEvent.timestamp >= recent_cutoff,
                    Token.created_at >= recent_cutoff,
                    TradeEvent.id.is_(None),  # No trades yet (newly deployed)
                    db.and_(  # Graduated tokens with DEX pools (always include)
                        Token.graduation_status == 'graduated',
                        Token.dex_pool_address.isnot(None)
                    ),
                    Token.reserved_percentage > 0  # PRO tokens (can receive airdrops anytime)
                )
            ).distinct().all()
            
            all_deployed = Token.query.filter(
                Token.contract_address.isnot(None),
                Token.deployment_status == 'deployed'
            ).count()
            
            logger.info(f"📊 Processing {len(deployed_tokens)} active tokens out of {all_deployed} total (cycle #{index_all_events._cycle_counter})")
        
        # STEP 2: Process tokens in parallel (5 workers)
        # Reduced from 10 to 5 to prevent network congestion and RPC rate limiting
        token_ids = [token.id for token in deployed_tokens]
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all token processing jobs
            future_to_token = {
                executor.submit(process_single_token, token_id, from_block, to_block): token_id 
                for token_id in token_ids
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_token):
                try:
                    result = future.result()
                    if result['success']:
                        summary['trades'] += result['trades']
                        summary['graduations'] += result['graduations']
                        summary['errors'] += result['errors']
                        summary['tokens_processed'] += 1
                except Exception as e:
                    logger.error(f"Thread execution error: {str(e)}")
                    summary['errors'] += 1
        
        grad_result = process_graduation_events(from_block, to_block)
        if grad_result.get('success'):
            grad_stats = grad_result.get('stats', {})
            summary['graduations'] += grad_stats.get('initiations', 0) + grad_stats.get('completions', 0)
            summary['errors'] += grad_stats.get('errors', 0)
            
            logger.debug(f"Graduation: {grad_stats.get('initiations', 0)} initiations, {grad_stats.get('completions', 0)} completions")
        
        summary['events_indexed'] = summary['trades'] + summary['graduations']
        
        set_last_indexed_block(to_block)
        
        logger.info(f"✅ Indexing complete: {summary['events_indexed']} events indexed, {summary['errors']} errors")
        logger.info(f"📈 Summary: {summary['tokens_deployed']} tokens deployed, {summary['trades']} trades, {summary['graduations']} graduations across {summary['tokens_processed']} tokens")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error indexing events: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'events_indexed': 0,
            'errors': 1
        }


if __name__ == "__main__":
    logger.info("Starting event indexer...")
    result = index_all_events()
    logger.info(f"Indexer result: {result}")
