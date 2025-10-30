"""Award achievements to Kryptoman based on their activity"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from services.achievement_service import evaluate_user_achievements

with app.app_context():
    print("Evaluating achievements for Kryptoman (user ID 23)...")
    results = evaluate_user_achievements(23)
    
    print(f"\nAchievements evaluated: {len(results)}")
    completed = [v for k, v in results.items() if v['is_completed']]
    print(f"Completed achievements: {len(completed)}")
    
    # Show completed achievements
    for achievement in completed:
        print(f"  ✅ {achievement['name']} - {achievement['reward']} GEM")
    
    # Get updated user stats
    from models import User
    user = User.query.get(23)
    print(f"\n📊 Kryptoman updated stats:")
    print(f"   GEM Points: {user.gem_points}")
    print(f"   Tokens Created: {user.total_tokens_created}")
    print(f"   Trading Volume: ${float(user.total_trading_volume or 0):,.2f}")
    print(f"   Total Trades: {user.total_trades_count}")
