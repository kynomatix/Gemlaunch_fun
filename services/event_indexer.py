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

from app import db
from models import Token, TradeEvent, AntiBotFeeTracker
from services.web3_service import Web3Service

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

INDEXER_STATE_FILE = Path("config/indexer_state.json")

def get_web3_service():
    """Get or create Web3Service instance"""
    if not hasattr(get_web3_service, '_instance'):
        get_web3_service._instance = Web3Service()
    return get_web3_service._instance


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


def process_tokens_purchased_event(event, token, w3):
    """Process TokensPurchased event and create TradeEvent"""
    try:
        args = event['args']
        tx_hash = event['transactionHash'].hex()
        block_number = event['blockNumber']
        
        block = w3.eth.get_block(block_number)
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
        
        db.session.add(trade_event)
        db.session.flush()
        
        token.trade_count = (token.trade_count or 0) + 1
        token.trading_volume_24h = (token.trading_volume_24h or 0) + total_kas
        
        unique_holders = db.session.query(TradeEvent.user_wallet_address)\
            .filter(TradeEvent.token_id == token.id)\
            .filter(TradeEvent.trade_type == 'buy')\
            .distinct().count()
        token.holder_count = unique_holders
        
        logger.debug(f"✅ Processed TokensPurchased: {tokens_out} tokens for {total_kas} KAS (tx: {tx_hash[:10]}...)")
        
        return trade_event
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower() and 'tx_hash' in str(e).lower():
            logger.debug(f"Skipping duplicate TokensPurchased event: {tx_hash}")
            db.session.rollback()
            return None
        raise
    except Exception as e:
        logger.error(f"Error processing TokensPurchased event: {str(e)}")
        db.session.rollback()
        raise


def process_tokens_sold_event(event, token, w3):
    """Process TokensSold event and create TradeEvent"""
    try:
        args = event['args']
        tx_hash = event['transactionHash'].hex()
        block_number = event['blockNumber']
        
        block = w3.eth.get_block(block_number)
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
        
        db.session.add(trade_event)
        db.session.flush()
        
        token.trade_count = (token.trade_count or 0) + 1
        token.trading_volume_24h = (token.trading_volume_24h or 0) + kas_out
        
        logger.debug(f"✅ Processed TokensSold: {tokens_in} tokens for {kas_out} KAS (tx: {tx_hash[:10]}...)")
        
        return trade_event
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower() and 'tx_hash' in str(e).lower():
            logger.debug(f"Skipping duplicate TokensSold event: {tx_hash}")
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
    """Process GraduationInitiated event from BondingCurvePool"""
    try:
        tx_hash = event['transactionHash'].hex()
        block_number = event['blockNumber']
        
        block = w3.eth.get_block(block_number)
        timestamp = datetime.fromtimestamp(block['timestamp'], tz=timezone.utc)
        
        args = event['args']
        kas_liquidity = Decimal(str(w3.from_wei(args['kasLiquidity'], 'ether')))
        token_liquidity = Decimal(str(args['tokenLiquidity']))
        
        token.is_graduated = True
        token.graduated_at = timestamp
        token.graduation_tx = tx_hash
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


def process_bonding_pool_events(pool_address, from_block, to_block):
    """Process all BondingCurvePool events for a token"""
    try:
        web3_service = get_web3_service()
        w3 = web3_service.w3
        
        token = Token.query.filter_by(contract_address=pool_address.lower()).first()
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
            'errors': 0
        }
        
        try:
            purchase_filter = pool_contract.events.TokensPurchased.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            purchase_events = purchase_filter.get_all_entries()
            
            for event in purchase_events:
                try:
                    trade_event = process_tokens_purchased_event(event, token, w3)
                    if trade_event:
                        stats['purchases'] += 1
                except Exception as e:
                    logger.error(f"Error processing purchase event: {str(e)}")
                    stats['errors'] += 1
                    continue
        except Exception as e:
            logger.error(f"Error fetching TokensPurchased events: {str(e)}")
        
        try:
            sell_filter = pool_contract.events.TokensSold.create_filter(
                from_block=from_block,
                to_block=to_block
            )
            sell_events = sell_filter.get_all_entries()
            
            for event in sell_events:
                try:
                    trade_event = process_tokens_sold_event(event, token, w3)
                    if trade_event:
                        stats['sells'] += 1
                except Exception as e:
                    logger.error(f"Error processing sell event: {str(e)}")
                    stats['errors'] += 1
                    continue
        except Exception as e:
            logger.error(f"Error fetching TokensSold events: {str(e)}")
        
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
        
        db.session.commit()
        
        return {'success': True, 'stats': stats}
        
    except Exception as e:
        logger.error(f"Error processing bonding pool events for {pool_address}: {str(e)}")
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
                    # Update with real pool/contract address (they're the same in BondingCurvePool)
                    token.contract_address = pool_address
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


def index_all_events(from_block=None, to_block='latest'):
    """
    Index all events from all contracts
    
    Args:
        from_block: Starting block number (defaults to last indexed block + 1)
        to_block: Ending block number (defaults to 'latest')
    
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
        
        # Sanity check: Warn if indexer is significantly behind
        blocks_behind = to_block - from_block
        if blocks_behind > 100:  # ~15 minutes at 6 sec blocks (Kasplex)
            logger.warning(f"⚠️ Event indexer {blocks_behind} blocks behind")
            logger.warning("Possible missed events during downtime - check manually if needed")
        
        logger.info(f"🔍 Indexing events from block {from_block} to {to_block}")
        
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
        
        # STEP 2: Query deployed tokens (they should have real addresses now)
        deployed_tokens = Token.query.filter(
            Token.contract_address.isnot(None),
            Token.deployment_status == 'deployed'
        ).all()
        
        logger.info(f"📊 Processing {len(deployed_tokens)} deployed tokens")
        
        for token in deployed_tokens:
            try:
                result = process_bonding_pool_events(
                    token.contract_address,
                    from_block,
                    to_block
                )
                
                if result.get('success'):
                    stats = result.get('stats', {})
                    summary['trades'] += stats.get('purchases', 0) + stats.get('sells', 0)
                    summary['graduations'] += stats.get('graduations', 0)
                    summary['errors'] += stats.get('errors', 0)
                    summary['tokens_processed'] += 1
                    
                    logger.debug(f"Token {token.symbol}: {stats.get('purchases', 0)} buys, {stats.get('sells', 0)} sells")
                else:
                    logger.error(f"Failed to process token {token.symbol}: {result.get('error')}")
                    summary['errors'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing token {token.symbol}: {str(e)}")
                summary['errors'] += 1
                continue
        
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
