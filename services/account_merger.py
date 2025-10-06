import logging
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logging.basicConfig(level=logging.DEBUG)

def merge_accounts(db, claimant_user_id, legacy_user_id):
    """
    Merge legacy user account into claimant user account.
    
    Architecture:
    - Claimant account survives
    - Legacy account data gets transferred to claimant
    - Sum additive fields (gem_points, totals)
    - Keep max-progress achievements
    - Legacy wallet address becomes a linked wallet for claimant
    - Legacy user remains active (not archived) but with null wallet_address
    
    Args:
        db: SQLAlchemy database instance
        claimant_user_id: ID of user who is claiming ownership (survives)
        legacy_user_id: ID of legacy user whose data will be merged
    
    Returns:
        dict: Summary of merge operation
    
    Raises:
        ValueError: If users don't exist or are invalid
        SQLAlchemyError: If database operation fails
    """
    from models import User, UserAchievement, TokenEngagement, LinkedWallet, Activity
    
    try:
        with db.session.begin_nested():
            claimant = User.query.get(claimant_user_id)
            legacy = User.query.get(legacy_user_id)
            
            if not claimant:
                raise ValueError(f"Claimant user {claimant_user_id} not found")
            if not legacy:
                raise ValueError(f"Legacy user {legacy_user_id} not found")
            if legacy.archived:
                raise ValueError(f"Legacy user {legacy_user_id} is already archived")
            if claimant.archived:
                raise ValueError(f"Claimant user {claimant_user_id} is archived")
            if claimant_user_id == legacy_user_id:
                raise ValueError("Cannot merge user with themselves")
            
            merge_summary = {
                'claimant_user_id': claimant_user_id,
                'legacy_user_id': legacy_user_id,
                'legacy_wallet': legacy.wallet_address,
                'merged_at': datetime.now(timezone.utc).isoformat(),
                'gem_points_added': 0,
                'achievements_transferred': 0,
                'achievements_merged': 0,
                'token_engagements_transferred': 0,
                'linked_wallets_transferred': 0,
                'skipped_linked_wallets': 0,
                'skipped_wallet_addresses': [],
                'activities_transferred': 0,
                'legacy_wallet_linked': False
            }
            
            logging.info(f"Starting account merge: claimant={claimant_user_id}, legacy={legacy_user_id}")
            
            claimant.gem_points = (claimant.gem_points or 0) + (legacy.gem_points or 0)
            merge_summary['gem_points_added'] = legacy.gem_points or 0
            
            claimant.total_tokens_created = (claimant.total_tokens_created or 0) + (legacy.total_tokens_created or 0)
            claimant.total_trading_volume = Decimal(claimant.total_trading_volume or 0) + Decimal(legacy.total_trading_volume or 0)
            claimant.total_graduated_tokens = (claimant.total_graduated_tokens or 0) + (legacy.total_graduated_tokens or 0)
            claimant.total_trades_count = (claimant.total_trades_count or 0) + (legacy.total_trades_count or 0)
            claimant.total_messages_sent = (claimant.total_messages_sent or 0) + (legacy.total_messages_sent or 0)
            claimant.longest_holding_days = max(claimant.longest_holding_days or 0, legacy.longest_holding_days or 0)
            
            legacy_achievements = UserAchievement.query.filter_by(user_id=legacy_user_id).all()
            for legacy_achievement in legacy_achievements:
                existing = UserAchievement.query.filter_by(
                    user_id=claimant_user_id,
                    achievement_id=legacy_achievement.achievement_id
                ).first()
                
                if existing:
                    if legacy_achievement.earned_at < existing.earned_at:
                        existing.earned_at = legacy_achievement.earned_at
                    merge_summary['achievements_merged'] += 1
                    db.session.delete(legacy_achievement)
                else:
                    legacy_achievement.user_id = claimant_user_id
                    merge_summary['achievements_transferred'] += 1
            
            legacy_engagements = TokenEngagement.query.filter_by(user_id=legacy_user_id).all()
            for legacy_engagement in legacy_engagements:
                existing = TokenEngagement.query.filter_by(
                    user_id=claimant_user_id,
                    token_id=legacy_engagement.token_id
                ).first()
                
                if existing:
                    existing.community_points = (existing.community_points or 0) + (legacy_engagement.community_points or 0)
                    existing.messages_sent = (existing.messages_sent or 0) + (legacy_engagement.messages_sent or 0)
                    existing.trades_count = (existing.trades_count or 0) + (legacy_engagement.trades_count or 0)
                    existing.total_traded_volume = Decimal(existing.total_traded_volume or 0) + Decimal(legacy_engagement.total_traded_volume or 0)
                    existing.polls_created = (existing.polls_created or 0) + (legacy_engagement.polls_created or 0)
                    existing.polls_voted = (existing.polls_voted or 0) + (legacy_engagement.polls_voted or 0)
                    existing.spotlight_messages = (existing.spotlight_messages or 0) + (legacy_engagement.spotlight_messages or 0)
                    existing.current_balance = Decimal(existing.current_balance or 0) + Decimal(legacy_engagement.current_balance or 0)
                    
                    if legacy_engagement.first_acquired_at:
                        if not existing.first_acquired_at or legacy_engagement.first_acquired_at < existing.first_acquired_at:
                            existing.first_acquired_at = legacy_engagement.first_acquired_at
                    
                    if legacy_engagement.last_activity_at > existing.last_activity_at:
                        existing.last_activity_at = legacy_engagement.last_activity_at
                    
                    db.session.delete(legacy_engagement)
                else:
                    legacy_engagement.user_id = claimant_user_id
                    merge_summary['token_engagements_transferred'] += 1
            
            claimant_linked_addresses = {lw.wallet_address.lower() for lw in LinkedWallet.query.filter_by(user_id=claimant_user_id).all()}
            
            legacy_linked_wallets = LinkedWallet.query.filter_by(user_id=legacy_user_id).all()
            for linked_wallet in legacy_linked_wallets:
                if linked_wallet.wallet_address.lower() not in claimant_linked_addresses:
                    linked_wallet.user_id = claimant_user_id
                    merge_summary['linked_wallets_transferred'] += 1
                else:
                    db.session.delete(linked_wallet)
                    merge_summary['skipped_linked_wallets'] += 1
                    merge_summary['skipped_wallet_addresses'].append(linked_wallet.wallet_address)
                    logging.info(f"Skipped duplicate linked wallet: {linked_wallet.wallet_address}")
            
            legacy_activities = Activity.query.filter_by(user_id=legacy_user_id).all()
            for activity in legacy_activities:
                activity.user_id = claimant_user_id
                merge_summary['activities_transferred'] += 1
            
            legacy_wallet_address = legacy.wallet_address
            # DO NOT set legacy.wallet_address = None - wallet_address is NOT NULL
            # The LinkedWallet entry will handle the linking
            
            if legacy_wallet_address:
                existing_linked_wallet = LinkedWallet.query.filter_by(
                    user_id=claimant_user_id,
                    wallet_address=legacy_wallet_address.lower()
                ).first()
                
                if not existing_linked_wallet:
                    new_linked_wallet = LinkedWallet(
                        user_id=claimant_user_id,
                        wallet_address=legacy_wallet_address.lower(),
                        status='verified'
                    )
                    db.session.add(new_linked_wallet)
                    merge_summary['legacy_wallet_linked'] = True
                    logging.info(f"Created LinkedWallet for legacy wallet: {legacy_wallet_address}")
                else:
                    merge_summary['legacy_wallet_linked'] = True
                    logging.info(f"Legacy wallet already linked to claimant: {legacy_wallet_address}")
            
            db.session.commit()
            
            logging.info(f"Account merge completed successfully: {merge_summary}")
            
            return merge_summary
            
    except IntegrityError as e:
        db.session.rollback()
        error_msg = f"Database integrity constraint violation during account merge: {str(e)}"
        logging.error(error_msg)
        raise ValueError(error_msg) from e
    except SQLAlchemyError as e:
        db.session.rollback()
        error_msg = f"Database error during account merge: {str(e)}"
        logging.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error during account merge: {str(e)}")
        raise
