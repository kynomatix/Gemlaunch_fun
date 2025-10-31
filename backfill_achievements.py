"""
Backfill missing achievements for users who should have them but don't
"""
from app import app, db
from models import User, Achievement
from services.achievement_service import award_achievement

def backfill_user_achievements(wallet_address):
    """Backfill missing achievements for a specific user"""
    with app.app_context():
        user = User.query.filter_by(wallet_address=wallet_address).first()
        if not user:
            print(f"User not found: {wallet_address}")
            return
        
        print(f"\n🔍 Checking user: {user.wallet_address}")
        print(f"Current stats:")
        print(f"  - Trades: {user.total_trades_count}")
        print(f"  - Trading Volume: {user.total_trading_volume}")
        print(f"  - Tokens Created: {user.total_tokens_created}")
        print(f"  - Graduated Tokens: {user.total_graduated_tokens}")
        print(f"  - Current GEM Points: {user.gem_points}")
        
        # Define achievements to check
        achievements_to_check = [
            ('First Trade', 'trades_count', 1),
            ('Steady Trader', 'trades_count', 10),
            ('Active Trader', 'trades_count', 50),
            ('Graduation Success', 'graduated_tokens', 1),
        ]
        
        awarded_count = 0
        total_points = 0
        
        for achievement_name, requirement_type, requirement_value in achievements_to_check:
            achievement = Achievement.query.filter_by(
                name=achievement_name,
                is_active=True
            ).first()
            
            if not achievement:
                print(f"⚠️  Achievement not found: {achievement_name}")
                continue
            
            # Check if user already has it
            from models import UserAchievement
            already_has = UserAchievement.query.filter_by(
                user_id=user.id,
                achievement_id=achievement.id
            ).first()
            
            if already_has:
                print(f"✅ {achievement_name} - Already awarded")
                continue
            
            # Check if user qualifies
            qualifies = False
            if requirement_type == 'trades_count':
                qualifies = user.total_trades_count >= requirement_value
            elif requirement_type == 'graduated_tokens':
                qualifies = user.total_graduated_tokens >= requirement_value
            
            if qualifies:
                print(f"🏆 Awarding: {achievement_name} (+{achievement.gem_points_reward} GEM)")
                result = award_achievement(user, achievement)
                if result:
                    awarded_count += 1
                    total_points += achievement.gem_points_reward
                else:
                    print(f"❌ Failed to award {achievement_name}")
            else:
                print(f"⏭️  {achievement_name} - User doesn't qualify yet")
        
        print(f"\n✨ Backfill complete!")
        print(f"   Awarded: {awarded_count} achievements")
        print(f"   Total GEM Points: +{total_points}")
        print(f"   New balance: {user.gem_points} GEM")

if __name__ == "__main__":
    # Backfill for the main user
    backfill_user_achievements('0xa51d8f597570353ae50a25df90ade162d2305ffa')
