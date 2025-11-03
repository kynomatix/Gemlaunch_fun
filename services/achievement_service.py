"""Achievement evaluation service for calculating user progress and auto-awarding achievements"""
from datetime import datetime, timezone
from sqlalchemy import func
from models import db, User, Token, Achievement, UserAchievement, Holding, Referral, Activity

try:
    from models_extended import ChatMessage
    CHAT_MESSAGES_AVAILABLE = True
except ImportError:
    CHAT_MESSAGES_AVAILABLE = False


# KASPERS NFT Contract Address (tKASPERS on Kasplex Testnet)
KASPERS_NFT_CONTRACT = "0x6a3B498EeD2A9F3498252bced7971FC4f3251322"  # tKASPERS NFT (KRC721)


def check_kaspers_nft_ownership(user):
    """
    Check if user holds KASPERS NFT (KRC721)
    
    Args:
        user: User object
        
    Returns:
        int: 1 if user holds at least one KASPERS NFT, 0 otherwise
    """
    try:
        # Import web3 service for blockchain queries
        from services.web3_service import get_web3_service
        
        # If placeholder address, return 0 for now
        if KASPERS_NFT_CONTRACT == "0x0000000000000000000000000000000000000000":
            return 0
        
        w3_service = get_web3_service()
        
        # ERC721 balanceOf ABI
        erc721_abi = [{
            "constant": True,
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }]
        
        # Create contract instance
        kaspers_contract = w3_service.w3.eth.contract(
            address=w3_service.w3.to_checksum_address(KASPERS_NFT_CONTRACT),
            abi=erc721_abi
        )
        
        # Query balance
        balance = kaspers_contract.functions.balanceOf(
            w3_service.w3.to_checksum_address(user.wallet_address)
        ).call()
        
        return 1 if balance > 0 else 0
    except Exception as e:
        print(f"Error checking KASPERS NFT ownership for user {user.id}: {e}")
        return 0


def calculate_user_progress(user, requirement_type):
    """
    Calculate user's current progress for a specific requirement type.
    
    Args:
        user: User object
        requirement_type: String indicating the type of requirement
        
    Returns:
        int or float: Current progress value
    """
    if requirement_type == 'tokens_created':
        return user.total_tokens_created or 0
    
    elif requirement_type == 'trading_volume':
        return float(user.total_trading_volume or 0)
    
    elif requirement_type == 'tokens_graduated':
        return user.total_graduated_tokens or 0
    
    elif requirement_type == 'total_trades':
        return user.total_trades_count or 0
    
    elif requirement_type in ['chat_messages_sent', 'messages_sent']:
        if CHAT_MESSAGES_AVAILABLE:
            return user.total_messages_sent or 0
        return 0
    
    elif requirement_type == 'likes_received':
        try:
            from models_extended import MessageReaction
            total_likes = db.session.query(func.count(MessageReaction.id)).join(
                ChatMessage, MessageReaction.message_id == ChatMessage.id
            ).filter(
                ChatMessage.user_id == user.id,
                MessageReaction.reaction_type == 'love'
            ).scalar() or 0
            return int(total_likes)
        except Exception as e:
            print(f"Error calculating likes_received: {e}")
            return 0
    
    elif requirement_type in ['referrals', 'referrals_made']:
        try:
            referral_count = Referral.query.filter(
                Referral.referrer_id == user.id,
                Referral.status == 'completed'
            ).count()
            return referral_count
        except Exception as e:
            print(f"Error calculating referrals: {e}")
            return 0
    
    elif requirement_type == 'top_contributor':
        try:
            from models_extended import Poll
            total_activity_score = (
                (user.total_messages_sent or 0) + 
                (Poll.query.filter_by(creator_id=user.id).count() * 2) +
                (user.total_tokens_created or 0) * 5
            )
            return total_activity_score >= 100
        except Exception as e:
            print(f"Error calculating top_contributor: {e}")
            return 0
    
    elif requirement_type == 'holding_days':
        try:
            holdings = Holding.query.filter(
                Holding.user_id == user.id,
                Holding.token_amount > 0
            ).all()
            
            if not holdings:
                return 0
            
            max_days = 0
            current_time = datetime.now(timezone.utc)
            
            for holding in holdings:
                if holding.first_purchase:
                    # Ensure both datetimes are timezone-aware for comparison
                    first_purchase = holding.first_purchase
                    if first_purchase.tzinfo is None:
                        # If naive, assume UTC and make it aware
                        first_purchase = first_purchase.replace(tzinfo=timezone.utc)
                    
                    days_held = (current_time - first_purchase).days
                    max_days = max(max_days, days_held)
            
            return max_days
        except Exception as e:
            print(f"Error calculating holding_days: {e}")
            return 0
    
    elif requirement_type == 'user_number':
        return user.id
    
    elif requirement_type == 'token_holders':
        try:
            tokens = Token.query.filter_by(creator_id=user.id).all()
            
            if not tokens:
                return 0
            
            max_holders = max((token.holder_count or 0 for token in tokens), default=0)
            return max_holders
        except Exception as e:
            print(f"Error calculating token_holders: {e}")
            return 0
    
    elif requirement_type == 'polls_created':
        try:
            from models_extended import Poll
            return float(Poll.query.filter_by(creator_id=user.id).count())
        except:
            return 0.0
    
    elif requirement_type == 'polls_voted':
        try:
            from models_extended import PollVote, Poll
            vote_count = db.session.query(PollVote).join(
                Poll, PollVote.poll_id == Poll.id
            ).filter(
                PollVote.user_id == user.id,
                Poll.creator_id != user.id
            ).count()
            return float(vote_count)
        except:
            return 0.0
    
    elif requirement_type == 'holds_kaspers_nft':
        # Check if user holds KASPERS NFT (KRC721)
        return check_kaspers_nft_ownership(user)
    
    return 0


def award_achievement(user, achievement):
    """
    Award an achievement to a user.
    
    Args:
        user: User object
        achievement: Achievement object
        
    Returns:
        UserAchievement: The created UserAchievement record
    """
    existing = UserAchievement.query.filter_by(
        user_id=user.id,
        achievement_id=achievement.id
    ).first()
    
    if existing:
        return existing
    
    user_achievement = UserAchievement(
        user_id=user.id,
        achievement_id=achievement.id
    )
    db.session.add(user_achievement)
    
    if achievement.gem_points_reward and achievement.gem_points_reward > 0:
        user.gem_points = (user.gem_points or 0) + achievement.gem_points_reward
    
    activity = Activity(
        user_id=user.id,
        activity_type='achievement_earned',
        title=f'Achievement Unlocked: {achievement.name}',
        description=f'Earned the "{achievement.name}" achievement: {achievement.description}',
        achievement_id=achievement.id,
        points_earned=achievement.gem_points_reward or 0,
        is_public=True
    )
    db.session.add(activity)
    
    try:
        db.session.commit()
        print(f"✨ Achievement awarded: {achievement.name} to user {user.id}")
        return user_achievement
    except Exception as e:
        db.session.rollback()
        print(f"Error awarding achievement: {e}")
        return None


def evaluate_user_achievements(user_id):
    """
    Evaluate all achievements for a user and award any that are completed.
    
    Args:
        user_id: ID of the user to evaluate
        
    Returns:
        dict: Mapping of achievement_id to progress information
    """
    user = User.query.get(user_id)
    if not user:
        return {}
    
    active_achievements = Achievement.query.filter_by(is_active=True).all()
    
    already_earned = {
        ua.achievement_id: ua.earned_at 
        for ua in UserAchievement.query.filter_by(user_id=user_id).all()
    }
    
    results = {}
    
    for achievement in active_achievements:
        current_progress = calculate_user_progress(user, achievement.requirement_type)
        requirement_value = float(achievement.requirement_value or 0)
        
        is_completed = False
        earned_at = None
        
        if achievement.id in already_earned:
            is_completed = True
            earned_at = already_earned[achievement.id]
        else:
            if requirement_value > 0:
                if achievement.requirement_type == 'user_number':
                    is_completed = current_progress <= requirement_value
                else:
                    is_completed = current_progress >= requirement_value
            else:
                is_completed = False
            
            if is_completed:
                user_achievement = award_achievement(user, achievement)
                if user_achievement:
                    earned_at = user_achievement.earned_at
        
        if requirement_value > 0:
            if achievement.requirement_type == 'user_number':
                progress_pct = 100 if is_completed else 0
            else:
                progress_pct = min(int((current_progress / requirement_value) * 100), 100)
        else:
            progress_pct = 100 if is_completed else 0
        
        results[achievement.id] = {
            'name': achievement.name,
            'description': achievement.description,
            'icon': achievement.icon,
            'category': achievement.category,
            'requirement_type': achievement.requirement_type,
            'progress': float(current_progress) if isinstance(current_progress, (int, float)) else current_progress,
            'requirement': float(requirement_value),
            'progress_pct': progress_pct,
            'is_completed': is_completed,
            'earned_at': earned_at,
            'reward': achievement.gem_points_reward or 0
        }
    
    return results


def batch_evaluate_achievements(user_ids):
    """
    Evaluate achievements for multiple users at once.
    
    Args:
        user_ids: List of user IDs to evaluate
        
    Returns:
        dict: Mapping of user_id to their achievement results
    """
    results = {}
    
    for user_id in user_ids:
        try:
            results[user_id] = evaluate_user_achievements(user_id)
        except Exception as e:
            print(f"Error evaluating achievements for user {user_id}: {e}")
            results[user_id] = {}
    
    return results


def get_achievement_summary(user_id):
    """
    Get a summary of user's achievement progress.
    
    Args:
        user_id: ID of the user
        
    Returns:
        dict: Summary statistics
    """
    results = evaluate_user_achievements(user_id)
    
    if not results:
        return {
            'total_achievements': 0,
            'earned_count': 0,
            'in_progress_count': 0,
            'completion_percentage': 0,
            'total_gem_points': 0,
            'by_category': {}
        }
    
    earned_count = sum(1 for r in results.values() if r['is_completed'])
    in_progress_count = sum(1 for r in results.values() if not r['is_completed'] and r['progress'] > 0)
    
    by_category = {}
    for achievement_data in results.values():
        category = achievement_data['category'] or 'uncategorized'
        if category not in by_category:
            by_category[category] = {
                'total': 0,
                'earned': 0,
                'in_progress': 0
            }
        
        by_category[category]['total'] += 1
        if achievement_data['is_completed']:
            by_category[category]['earned'] += 1
        elif achievement_data['progress'] > 0:
            by_category[category]['in_progress'] += 1
    
    user = User.query.get(user_id)
    total_gem_points = user.gem_points if user else 0
    
    return {
        'total_achievements': len(results),
        'earned_count': earned_count,
        'in_progress_count': in_progress_count,
        'completion_percentage': int((earned_count / len(results)) * 100) if results else 0,
        'total_gem_points': total_gem_points,
        'by_category': by_category
    }
