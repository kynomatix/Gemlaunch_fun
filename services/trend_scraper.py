"""
4chan /biz/ trend scraper for Gemmy Zeroday Memification Engine
Scrapes 4chan /biz/ board for trending meme coins
"""

import re
from datetime import datetime, timedelta, timezone
import logging

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


def scrape_4chan_biz():
    """
    Scrape 4chan /biz/ board for trending meme coins
    
    Returns:
        list: List of meme dictionaries with structure:
            {
                'title': str,
                'keywords': list,  # Contains tickers like $TICKER, terms like "moon", "gem"
                'reply_count': int,
                'timestamp': datetime,
                'source': '4chan_biz'
            }
    """
    if requests is None:
        logger.warning("requests library not available, returning empty list")
        return []
    
    try:
        api_url = "https://a.4cdn.org/biz/catalog.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        catalog = response.json()
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=12)
        trends = []
        
        for page in catalog:
            threads = page.get('threads', [])
            
            for thread in threads:
                reply_count = thread.get('replies', 0)
                
                if reply_count <= 10:
                    continue
                
                thread_time = datetime.fromtimestamp(thread.get('time', 0), tz=timezone.utc)
                
                if thread_time < cutoff_time:
                    continue
                
                subject = thread.get('sub', '')
                comment = thread.get('com', '')
                
                title = subject if subject else _extract_first_line(comment)
                
                full_text = f"{subject} {comment}"
                keywords = _extract_keywords(full_text)
                
                if keywords:
                    trends.append({
                        'title': _clean_html(title),
                        'keywords': keywords,
                        'reply_count': reply_count,
                        'timestamp': thread_time,
                        'source': '4chan_biz'
                    })
        
        trends.sort(key=lambda x: x['reply_count'], reverse=True)
        
        logger.info(f"Scraped {len(trends)} trending memes from 4chan /biz/")
        return trends[:50]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping 4chan /biz/: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in scrape_4chan_biz: {e}")
        return []


def _extract_keywords(text):
    """Extract ticker symbols and meme keywords from text"""
    if not text:
        return []
    
    keywords = []
    
    text_clean = _clean_html(text)
    
    ticker_pattern = r'\$[A-Z]{2,10}\b'
    tickers = re.findall(ticker_pattern, text_clean)
    keywords.extend(tickers)
    
    meme_keywords = ['moon', 'gem', 'rocket', 'lambo', 'wen', 'hodl', 'diamond', 'hands', 'pump']
    text_lower = text_clean.lower()
    
    for keyword in meme_keywords:
        if keyword in text_lower:
            keywords.append(keyword)
    
    return list(set(keywords))


def _clean_html(text):
    """Remove HTML tags from text"""
    if not text:
        return ""
    
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#039;', "'", text)
    text = re.sub(r'&amp;', '&', text)
    
    return text.strip()


def _extract_first_line(text):
    """Extract first meaningful line from text"""
    if not text:
        return "Untitled Thread"
    
    clean = _clean_html(text)
    lines = clean.split('\n')
    
    for line in lines:
        line = line.strip()
        if len(line) > 10:
            return line[:200]
    
    return clean[:200] if clean else "Untitled Thread"
