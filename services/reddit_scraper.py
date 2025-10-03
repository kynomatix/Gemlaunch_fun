"""
Reddit /r/CryptoMoonShots scraper for Gemmy Zeroday Memification Engine
Scrapes Reddit for trending moonshot posts
"""

import re
from datetime import datetime, timedelta, timezone
import logging

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


def scrape_reddit_moonshots():
    """
    Scrape Reddit /r/CryptoMoonShots for rising posts
    
    Returns:
        list: List of meme dictionaries with structure:
            {
                'title': str,
                'upvotes': int,
                'comments': int,
                'keywords': list,  # Ticker symbols extracted
                'timestamp': datetime,
                'source': 'reddit_moonshots'
            }
    """
    if requests is None:
        logger.warning("requests library not available, returning empty list")
        return []
    
    try:
        url = "https://www.reddit.com/r/CryptoMoonShots/rising.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=12)
        trends = []
        
        posts = data.get('data', {}).get('children', [])
        
        for post in posts:
            post_data = post.get('data', {})
            
            created_utc = post_data.get('created_utc', 0)
            post_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            
            if post_time < cutoff_time:
                continue
            
            title = post_data.get('title', '')
            selftext = post_data.get('selftext', '')
            upvotes = post_data.get('ups', 0)
            num_comments = post_data.get('num_comments', 0)
            
            full_text = f"{title} {selftext}"
            keywords = _extract_tickers(full_text)
            
            if keywords or 'gem' in title.lower() or 'moon' in title.lower():
                trends.append({
                    'title': title,
                    'upvotes': upvotes,
                    'comments': num_comments,
                    'keywords': keywords,
                    'timestamp': post_time,
                    'source': 'reddit_moonshots'
                })
        
        trends.sort(key=lambda x: x['upvotes'] + (x['comments'] * 2), reverse=True)
        
        logger.info(f"Scraped {len(trends)} trending posts from Reddit /r/CryptoMoonShots")
        return trends[:50]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping Reddit: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in scrape_reddit_moonshots: {e}")
        return []


def _extract_tickers(text):
    """Extract ticker symbols from text"""
    if not text:
        return []
    
    ticker_pattern = r'\$?[A-Z]{2,10}(?=\s|$|[^\w])'
    
    potential_tickers = re.findall(ticker_pattern, text)
    
    common_words = {'THE', 'AND', 'FOR', 'NOT', 'BUT', 'OR', 'AT', 'TO', 'IN', 'ON', 'IS', 'IT', 'BE', 'BY', 'AS', 'AN', 'IF', 'OF', 'SO', 'DO', 'GO', 'NO', 'MY', 'UP', 'ME', 'WE', 'HE', 'SHE', 'YOU', 'NEW', 'OLD', 'BIG', 'LOW', 'HIGH', 'ALL', 'ANY', 'FEW', 'GET', 'HAS', 'HAD', 'HOW', 'ITS', 'MAY', 'OUR', 'OUT', 'OWN', 'SAY', 'SEE', 'CAN', 'COULD', 'WOULD', 'SHOULD', 'WILL', 'MUST', 'HAVE', 'BEEN', 'WHEN', 'WHERE', 'WHAT', 'WHICH', 'WHO', 'WHY', 'THEIR', 'THERE', 'THESE', 'THOSE', 'THEN', 'THAN', 'THIS', 'THAT', 'WITH', 'FROM', 'ABOUT', 'AFTER', 'BEFORE', 'BETWEEN'}
    
    tickers = []
    for ticker in potential_tickers:
        ticker_clean = ticker.replace('$', '').strip()
        
        if len(ticker_clean) >= 2 and ticker_clean not in common_words:
            tickers.append(f"${ticker_clean}")
    
    return list(set(tickers))
