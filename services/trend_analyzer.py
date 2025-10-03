"""
Trend Analyzer for Gemmy Zeroday Memification Engine
Scores memes based on 7 crypto-adoptability criteria using AI
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone

def score_meme_with_ai(meme_data):
    """
    Score a meme using AI based on 7 crypto-adoptability criteria:
    1. Viral Potential
    2. Cultural Timing
    3. Community Signal
    4. Crypto-Native Elements
    5. Symbol/Mascot Strength
    6. Moggability
    7. Low Cringe Factor
    
    Returns: dict with scores and overall rating
    """
    
    prompt = f"""Analyze this meme for crypto memecoin potential. Score each criterion 0-10:

Meme: {meme_data.get('title', '')}
Source: {meme_data.get('source', 'unknown')}
Engagement: {meme_data.get('replies', 0)} replies, {meme_data.get('upvotes', 0)} upvotes
Keywords: {', '.join(meme_data.get('keywords', []))}

Score these 7 criteria (0-10 each):
1. VIRAL POTENTIAL: Is it simple, catchy, and remixable?
2. CULTURAL TIMING: Riding existing trends? Counter-narrative appeal?
3. COMMUNITY SIGNAL: Strong engagement and ticker mentions?
4. CRYPTO-NATIVE: Financial angle, degen appeal, anti-establishment?
5. MASCOT STRENGTH: Recognizable mascot, 3-5 letter ticker potential?
6. MOGGABILITY: Can it dominate others? First-mover advantage?
7. LOW CRINGE: Organic, authentic, self-aware humor (not forced)?

KASPA BONUS: If it has Kaspa tech relevance (GHOSTDAG, DAGKnight, BlockDAG, 10 BPS), add +15% to total.

Respond ONLY in JSON format:
{{
  "viral_potential": <score>,
  "cultural_timing": <score>,
  "community_signal": <score>,
  "crypto_native": <score>,
  "mascot_strength": <score>,
  "moggability": <score>,
  "cringe_factor": <score>,
  "kaspa_bonus": <true/false>,
  "overall_score": <weighted average>,
  "reasoning": "<brief explanation>",
  "suggested_ticker": "<3-5 letter ticker>"
}}"""
    
    try:
        api_token = os.environ.get('REPLICATE_API_TOKEN')
        if not api_token:
            return create_default_score(meme_data)
        
        response = requests.post(
            'https://api.replicate.com/v1/predictions',
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
            },
            json={
                'version': '0883e21444dd2c2b1ce02e17d63bc0a84a4d57c3b1e68a29c69f3ef0fb59e60a',
                'input': {
                    'prompt': prompt,
                    'max_tokens': 500,
                    'temperature': 0.3,
                }
            },
            timeout=30
        )
        
        if response.status_code == 201:
            prediction = response.json()
            prediction_id = prediction.get('id')
            
            for _ in range(10):
                import time
                time.sleep(1)
                
                status_response = requests.get(
                    f'https://api.replicate.com/v1/predictions/{prediction_id}',
                    headers={'Authorization': f'Bearer {api_token}'},
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    result = status_response.json()
                    if result.get('status') == 'succeeded':
                        output = ''.join(result.get('output', []))
                        
                        json_start = output.find('{')
                        json_end = output.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = output[json_start:json_end]
                            scores = json.loads(json_str)
                            scores['meme_data'] = meme_data
                            return scores
                        break
                    elif result.get('status') == 'failed':
                        break
        
        return create_default_score(meme_data)
        
    except Exception as e:
        print(f"Error scoring meme: {e}")
        return create_default_score(meme_data)

def create_default_score(meme_data):
    """Create a default score based on engagement metrics"""
    replies = meme_data.get('replies', 0)
    upvotes = meme_data.get('upvotes', 0)
    keywords = meme_data.get('keywords', [])
    
    engagement_score = min((replies + upvotes) / 10, 10)
    
    keyword_score = 0
    if any(k.lower() in ['moon', 'gem', '100x'] for k in keywords):
        keyword_score += 2
    if any(k.startswith('$') for k in keywords):
        keyword_score += 3
    
    base_score = (engagement_score + keyword_score) / 2
    
    return {
        'viral_potential': base_score,
        'cultural_timing': base_score,
        'community_signal': engagement_score,
        'crypto_native': keyword_score,
        'mascot_strength': 5,
        'moggability': base_score,
        'cringe_factor': 7,
        'kaspa_bonus': False,
        'overall_score': base_score,
        'reasoning': 'Scored based on engagement metrics (AI unavailable)',
        'suggested_ticker': '',
        'meme_data': meme_data
    }

def analyze_and_rank_trends(scraped_trends, top_n=5):
    """
    Analyze scraped trends and return top N ranked by score
    """
    scored_trends = []
    
    for trend in scraped_trends:
        score_result = score_meme_with_ai(trend)
        scored_trends.append(score_result)
    
    scored_trends.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
    
    return scored_trends[:top_n]

def get_trending_memes():
    """
    Main function to get trending memes
    Checks cache first, then scrapes and scores if needed
    """
    from services.trend_scraper import scrape_4chan_biz
    from services.reddit_scraper import scrape_reddit_moonshots
    from models import TrendCache, db
    
    cache = TrendCache.get_or_refresh('external_trends')
    
    if cache and cache.scored_trends:
        return cache.scored_trends
    
    all_trends = []
    all_trends.extend(scrape_4chan_biz())
    all_trends.extend(scrape_reddit_moonshots())
    
    if not all_trends:
        return []
    
    scored = analyze_and_rank_trends(all_trends, top_n=5)
    
    new_cache = TrendCache(
        cache_type='external_trends',
        trends_data=all_trends,
        scored_trends=scored,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
    )
    db.session.add(new_cache)
    
    TrendCache.cleanup_old_entries()
    
    db.session.commit()
    
    return scored
