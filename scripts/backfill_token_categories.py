"""
Backfill Token Categories Script

This script automatically categorizes all existing tokens using AI.
Returns multiple categories per token (up to 3).
Categories: Animals, Holidays, Tech, Finance, PopCulture, Food, Sports, Nature, Abstract, Community

Usage:
    python scripts/backfill_token_categories.py
"""

import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from models import Token
from services.token_categorizer import categorize_token_with_fallback

def backfill_token_categories():
    """Categorize all existing tokens using AI"""
    
    with app.app_context():
        print("=" * 70)
        print("BACKFILLING TOKEN CATEGORIES WITH AI")
        print("=" * 70)
        
        # Get all visible tokens
        tokens = Token.query.filter_by(
            is_visible=True,
            deployment_status='deployed'
        ).all()
        
        print(f"\nFound {len(tokens)} tokens to categorize")
        print("\nStarting categorization (using Llama 3.1 8B via OpenRouter)...")
        print("Estimated cost: ~${:.4f} (${:.6f} per token)\n".format(
            len(tokens) * 0.00015, 
            0.00015
        ))
        
        updated_count = 0
        category_stats = {}
        
        for idx, token in enumerate(tokens, 1):
            symbol = token.symbol or 'UNKNOWN'
            name = token.name or ''
            description = token.description or ''
            
            print(f"[{idx}/{len(tokens)}] ${symbol} - {name[:30]}...")
            
            # Get AI categorization (returns list)
            try:
                old_categories = json.loads(token.categories) if token.categories else ['Community']
            except:
                old_categories = ['Community']
                
            new_categories = categorize_token_with_fallback(name, symbol, description)
            
            # Update token
            token.categories = json.dumps(new_categories)
            
            # Track statistics (each category counted separately)
            for category in new_categories:
                category_stats[category] = category_stats.get(category, 0) + 1
            
            # Show result
            if set(old_categories) != set(new_categories):
                print(f"   ✅ {old_categories} → {new_categories}")
                updated_count += 1
            else:
                print(f"   ⚪ Kept: {new_categories}")
        
        # Commit all changes
        db.session.commit()
        
        print("\n" + "=" * 70)
        print(f"✅ CATEGORIZATION COMPLETE")
        print(f"   Updated {updated_count} tokens")
        print("=" * 70)
        
        # Show category distribution
        print("\n📊 CATEGORY DISTRIBUTION:")
        print("-" * 70)
        
        for category in sorted(category_stats.keys(), key=lambda c: category_stats[c], reverse=True):
            count = category_stats[category]
            percentage = (count / len(tokens) * 100) if tokens else 0
            bar = '█' * int(percentage / 2)
            print(f"{category:15s} | {bar:25s} {count:3d} ({percentage:5.1f}%)")
        
        print("-" * 70)
        print(f"Total: {len(tokens)} tokens")
        print("-" * 70)
        
        # Show some examples from each category
        print("\n🎯 SAMPLE TOKENS BY CATEGORY:")
        print("-" * 70)
        
        for category in sorted(category_stats.keys()):
            # Find tokens that include this category
            all_tokens = Token.query.filter_by(
                is_visible=True,
                deployment_status='deployed'
            ).all()
            
            category_tokens = []
            for t in all_tokens:
                try:
                    token_cats = json.loads(t.categories) if t.categories else []
                    if category in token_cats:
                        category_tokens.append(t)
                        if len(category_tokens) >= 3:
                            break
                except:
                    continue
            
            if category_tokens:
                print(f"\n{category}:")
                for t in category_tokens:
                    try:
                        all_cats = json.loads(t.categories)
                        cats_str = ', '.join(all_cats)
                        print(f"  • ${t.symbol} - {t.name} [{cats_str}]")
                    except:
                        print(f"  • ${t.symbol} - {t.name}")
        
        print("\n" + "=" * 70)

if __name__ == '__main__':
    backfill_token_categories()
