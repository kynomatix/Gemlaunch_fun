"""
Trend Analyzer for Gemmy Zeroday Memification Engine
Scores memes based on 7 crypto-adoptability criteria using AI
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    
    # Normalize engagement data from different sources
    replies = meme_data.get('replies', meme_data.get('reply_count', meme_data.get('comments', 0)))
    upvotes = meme_data.get('upvotes', 0)
    
    prompt = f"""Analyze this meme for crypto memecoin potential. Score each criterion 0-10:

Meme: {meme_data.get('title', '')}
Source: {meme_data.get('source', 'unknown')}
Engagement: {replies} replies/comments, {upvotes} upvotes
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
        api_token = os.environ.get('OPENROUTER')
        if not api_token:
            return create_default_score(meme_data)
        
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://gemlaunch.fun',
                'X-Title': 'Gemlaunch.fun'
            },
            json={
                'model': 'meta-llama/llama-3.1-70b-instruct',
                'messages': [
                    {'role': 'system', 'content': 'You are a crypto meme analyst. Respond ONLY in valid JSON format.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 500
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        output = result['choices'][0]['message']['content']
        
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = output[json_start:json_end]
            scores = json.loads(json_str)
            scores['meme_data'] = meme_data
            return scores
        
        return create_default_score(meme_data)
        
    except Exception as e:
        print(f"Error scoring meme: {e}")
        return create_default_score(meme_data)

def create_default_score(meme_data):
    """Create a default score based on source type and available metrics"""
    source = meme_data.get('source', 'unknown')
    
    # Different scoring logic based on source type
    if source == 'knowyourmeme':
        # KnowYourMeme: High base score for NEW trending memes
        status = meme_data.get('status', '')
        is_new = 'new' in status.lower() or 'trending' in status.lower()
        
        base_score = 7.5 if is_new else 6.5  # High score for fresh memes
        
        return {
            'viral_potential': 8.0,  # KYM entries are pre-validated as viral
            'cultural_timing': 9.0 if is_new else 7.0,  # NEW = perfect timing
            'community_signal': 7.0,
            'crypto_native': 5.0,  # Neutral - not crypto-specific yet
            'mascot_strength': 7.0,  # KYM memes usually have strong mascots
            'moggability': base_score,
            'cringe_factor': 8.0,
            'kaspa_bonus': False,
            'overall_score': base_score,
            'reasoning': 'Fresh meme from KnowYourMeme - high viral potential (AI unavailable)',
            'suggested_ticker': '',
            'meme_data': meme_data
        }
    
    elif source.startswith('4chan_') and source != '4chan_biz':
        # 4chan culture boards: Score based on cultural signal type
        cultural_signal = meme_data.get('cultural_signal', 'unknown')
        replies = meme_data.get('reply_count', 0)
        
        signal_scores = {
            'mascot': 8.0,
            'catchphrase': 7.5,
            'viral_moment': 7.0,
            'meme_format': 6.5,
            'character': 7.5,
            'unknown': 5.0
        }
        
        base_score = signal_scores.get(cultural_signal, 5.0)
        engagement_boost = min(replies / 100, 2.0)  # Up to +2 for high engagement
        
        return {
            'viral_potential': base_score + engagement_boost,
            'cultural_timing': 8.0,  # Culture boards = early timing
            'community_signal': min(replies / 20, 10),
            'crypto_native': 4.0,  # Pre-coin content
            'mascot_strength': 8.0 if cultural_signal == 'mascot' else 6.0,
            'moggability': base_score,
            'cringe_factor': 7.0,
            'kaspa_bonus': False,
            'overall_score': base_score + engagement_boost,
            'reasoning': f'Emerging {cultural_signal} from {source} (AI unavailable)',
            'suggested_ticker': '',
            'meme_data': meme_data
        }
    
    else:
        # /biz/ and Reddit: Traditional engagement-based scoring
        replies = meme_data.get('replies', meme_data.get('reply_count', meme_data.get('comments', 0)))
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
    Uses fallback scoring first to pre-filter, then AI scores top candidates in PARALLEL
    """
    # First pass: Quick fallback scoring for all trends
    quick_scored = []
    for trend in scraped_trends:
        fallback_score = create_default_score(trend)
        quick_scored.append(fallback_score)
    
    # Sort by fallback scores and take top 20 candidates
    quick_scored.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
    top_candidates = quick_scored[:20]  # AI-score top 20 candidates
    
    # Second pass: PARALLEL AI scoring for top candidates (if API available)
    final_scored = []
    
    def score_with_fallback(candidate):
        """Helper to score with AI or fall back to quick score"""
        try:
            return score_meme_with_ai(candidate['meme_data'])
        except:
            return candidate
    
    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all scoring tasks in parallel
        future_to_candidate = {
            executor.submit(score_with_fallback, candidate): candidate 
            for candidate in top_candidates
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_candidate):
            try:
                result = future.result()
                final_scored.append(result)
            except Exception as e:
                # If something goes wrong, use the fallback score
                candidate = future_to_candidate[future]
                final_scored.append(candidate)
    
    # Final sort and return top N
    final_scored.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
    
    return final_scored[:top_n]

def serialize_for_json(obj):
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj

def get_trending_memes():
    """
    Main function to get trending memes
    Checks cache first, then scrapes and scores if needed
    
    Sources (in priority order):
    1. Know Your Meme - New/trending memes (pre-coin)
    2. 4chan culture boards (/pol/, /tv/, /b/) - Emerging cultural trends
    3. 4chan /biz/ - Coin discussions (late-stage)
    4. Reddit CryptoMoonShots - Community validation (late-stage)
    """
    from services.trend_scraper import scrape_4chan_biz, scrape_4chan_culture_boards
    from services.reddit_scraper import scrape_reddit_moonshots
    from services.knowyourmeme_scraper import scrape_knowyourmeme
    from models import TrendCache, db
    
    cache = TrendCache.get_or_refresh('external_trends')
    
    if cache and cache.scored_trends:
        return cache.scored_trends
    
    all_trends = []
    
    # Priority 1: Know Your Meme (NEW memes before coins)
    all_trends.extend(scrape_knowyourmeme())
    
    # Priority 2: 4chan culture boards (emerging cultural trends)
    all_trends.extend(scrape_4chan_culture_boards())
    
    # Priority 3: Traditional sources (established coin discussions)
    all_trends.extend(scrape_4chan_biz())
    all_trends.extend(scrape_reddit_moonshots())
    
    if not all_trends:
        return []
    
    scored = analyze_and_rank_trends(all_trends, top_n=5)
    
    # Serialize datetime objects to strings for JSON storage
    trends_data_json = serialize_for_json(all_trends)
    scored_trends_json = serialize_for_json(scored)
    
    new_cache = TrendCache(
        cache_type='external_trends',
        trends_data=trends_data_json,
        scored_trends=scored_trends_json,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
    )
    db.session.add(new_cache)
    
    TrendCache.cleanup_old_entries()
    
    db.session.commit()
    
    return scored
