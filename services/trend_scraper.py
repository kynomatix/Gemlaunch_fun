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
                
                # Filter for meme-related content only
                if not _is_meme_related(full_text):
                    continue
                
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


def scrape_4chan_culture_boards():
    """
    Scrape 4chan culture boards (/pol/, /tv/, /b/) for emerging cultural trends
    that could become memes BEFORE they become coins
    
    Returns:
        list: List of cultural trend dictionaries with structure:
            {
                'title': str,
                'keywords': list,  # Contains character names, catchphrases, etc.
                'reply_count': int,
                'timestamp': datetime,
                'source': '4chan_pol' or '4chan_tv' or '4chan_b',
                'cultural_signal': str  # 'mascot', 'catchphrase', 'viral_moment', etc.
            }
    """
    if requests is None:
        logger.warning("requests library not available, returning empty list")
        return []
    
    boards = [
        ('pol', '4chan_pol'),
        ('tv', '4chan_tv'),
        ('b', '4chan_b')
    ]
    
    all_trends = []
    
    for board_name, source_name in boards:
        try:
            api_url = f"https://a.4cdn.org/{board_name}/catalog.json"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            catalog = response.json()
            
            # 24 hour cutoff for cultural boards
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            for page in catalog:
                threads = page.get('threads', [])
                
                for thread in threads:
                    reply_count = thread.get('replies', 0)
                    
                    # Higher engagement threshold for cultural boards
                    if reply_count <= 50:
                        continue
                    
                    thread_time = datetime.fromtimestamp(thread.get('time', 0), tz=timezone.utc)
                    
                    if thread_time < cutoff_time:
                        continue
                    
                    subject = thread.get('sub', '')
                    comment = thread.get('com', '')
                    
                    title = subject if subject else _extract_first_line(comment)
                    
                    full_text = f"{subject} {comment}"
                    
                    # Check for viral/memetic potential (NO coin requirement)
                    if not _has_viral_potential(full_text):
                        continue
                    
                    # Extract cultural keywords (character names, catchphrases, etc.)
                    keywords = _extract_cultural_keywords(full_text)
                    
                    # Detect what type of cultural signal this is
                    cultural_signal = _detect_cultural_signal(full_text, subject, comment)
                    
                    if keywords or cultural_signal:
                        all_trends.append({
                            'title': _clean_html(title),
                            'keywords': keywords,
                            'reply_count': reply_count,
                            'timestamp': thread_time,
                            'source': source_name,
                            'cultural_signal': cultural_signal
                        })
            
            logger.info(f"Scraped {len([t for t in all_trends if t['source'] == source_name])} cultural trends from 4chan /{board_name}/")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping 4chan /{board_name}/: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping /{board_name}/: {e}")
    
    # Sort by engagement
    all_trends.sort(key=lambda x: x['reply_count'], reverse=True)
    
    logger.info(f"Total cultural trends scraped: {len(all_trends)}")
    return all_trends[:50]


def _has_viral_potential(text):
    """
    Check if content has viral/memetic potential
    NO coin/crypto requirement - looking for PRE-COIN cultural signals
    """
    if not text or len(text) < 20:
        return False
    
    text_lower = _clean_html(text).lower()
    
    # Exclude obvious spam/low-quality
    spam_excludes = [
        'buy now', 'click here', 'limited time', 'act now',
        'telegram group', 'discord server',
        'porn', 'onlyfans', 'escort'
    ]
    
    for exclude in spam_excludes:
        if exclude in text_lower:
            return False
    
    # Viral indicators - things that spread organically
    viral_indicators = [
        # Character/mascot indicators
        'new character', 'mascot', 'cartoon', 'anime character',
        'character design', 'oc ', 'original character',
        
        # Catchphrase indicators
        'everyone is saying', 'people are saying', 'new phrase',
        'catchphrase', 'saying this now', 'new slang',
        
        # Viral spread indicators
        'going viral', 'trending', 'everywhere now', 'blowing up',
        'all over', 'spreading fast', 'caught on',
        
        # Remix/variation indicators
        'variations', 'remixes', 'edits', 'different versions',
        'spinoff', 'parody', 'derivative',
        
        # Image/visual indicators
        'reaction image', 'new meme', 'meme format', 'template',
        'exploitable', 'edit this', 'shop this',
        
        # Organic growth indicators
        'just noticed', 'keep seeing', 'seeing this everywhere',
        'started noticing', 'popping up'
    ]
    
    matches = sum(1 for indicator in viral_indicators if indicator in text_lower)
    
    # Also check for repeated patterns (indicates a catchphrase)
    repeated_patterns = _find_repeated_phrases(text_lower)
    
    # Also check for character name patterns (capitalized words, unique names)
    has_character_name = bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b(?:\s+(?:the|character|mascot|guy|girl|man|woman))', text))
    
    # Need at least one strong viral indicator OR repeated patterns OR character mention
    return matches >= 1 or len(repeated_patterns) > 0 or has_character_name


def _extract_cultural_keywords(text):
    """
    Extract cultural keywords: character names, catchphrases, viral phrases
    Different from coin keywords - NO ticker symbols
    """
    if not text:
        return []
    
    keywords = []
    text_clean = _clean_html(text)
    text_lower = text_clean.lower()
    
    # Character/mascot related terms
    character_terms = [
        'frog', 'pepe', 'wojak', 'chad', 'soyjak', 
        'gigachad', 'doomer', 'boomer', 'zoomer', 'coomer',
        'grinch', 'batman', 'joker', 'goku', 'spongebob',
        'shrek', 'mario', 'luigi', 'bowser', 'sonic',
        'pickle rick', 'morty', 'jerry', 'newman'
    ]
    
    for term in character_terms:
        if term in text_lower:
            keywords.append(term)
    
    # Extract proper nouns (potential character names)
    proper_nouns = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b', text_clean)
    # Filter to reasonable length and exclude common words
    common_words = {'The', 'This', 'That', 'What', 'When', 'Where', 'Why', 'How', 'Thread', 'Post'}
    proper_nouns = [n for n in proper_nouns if n not in common_words and len(n) > 2]
    keywords.extend(proper_nouns[:5])  # Limit to top 5
    
    # Viral phrase patterns (things in quotes, repeated phrases)
    quoted_phrases = re.findall(r'"([^"]{3,30})"', text_clean)
    keywords.extend(quoted_phrases[:3])  # Limit to top 3
    
    # Look for catchphrases (short repeated patterns)
    repeated = _find_repeated_phrases(text_lower)
    keywords.extend(repeated[:3])
    
    # Memetic terms
    meme_culture_terms = [
        'based', 'cringe', 'kek', 'lmao', 'cope', 'seethe',
        'dilate', 'rent free', 'touch grass', 'yikes',
        'oof', 'bruh', 'fr fr', 'no cap', 'bussin',
        'slaps', 'hits different', 'built different'
    ]
    
    for term in meme_culture_terms:
        if term in text_lower:
            keywords.append(term)
    
    return list(set(keywords))[:15]  # Return unique, limit to 15


def _detect_cultural_signal(full_text, subject, comment):
    """
    Detect what type of cultural signal this represents
    Returns: 'mascot', 'catchphrase', 'viral_moment', 'character', 'meme_format', or 'unknown'
    """
    text_lower = _clean_html(full_text).lower()
    
    # Mascot/character signals
    mascot_indicators = [
        'mascot', 'character', 'oc ', 'original character',
        'cartoon', 'design', 'frog', 'wojak', 'pepe',
        'anime girl', 'anime character', 'waifu'
    ]
    
    if any(ind in text_lower for ind in mascot_indicators):
        return 'mascot'
    
    # Catchphrase signals
    catchphrase_indicators = [
        'saying', 'phrase', 'everyone says', 'people say',
        'catchphrase', 'slogan', 'tagline', '"'
    ]
    
    has_quotes = '"' in full_text
    if has_quotes or any(ind in text_lower for ind in catchphrase_indicators):
        return 'catchphrase'
    
    # Viral moment signals
    viral_moment_indicators = [
        'going viral', 'blew up', 'trending', 'just happened',
        'breaking', 'did you see', 'cant believe', 'holy shit'
    ]
    
    if any(ind in text_lower for ind in viral_moment_indicators):
        return 'viral_moment'
    
    # Meme format signals
    meme_format_indicators = [
        'template', 'format', 'reaction image', 'exploitable',
        'edit this', 'shop this', 'make one', 'post your'
    ]
    
    if any(ind in text_lower for ind in meme_format_indicators):
        return 'meme_format'
    
    # Character signals (specific named entities)
    has_character_name = bool(re.search(r'\b[A-Z][a-z]+\s+(?:the|character|guy|girl)', full_text))
    if has_character_name:
        return 'character'
    
    return 'unknown'


def _find_repeated_phrases(text):
    """Find short phrases that appear multiple times (potential catchphrases)"""
    if not text or len(text) < 10:
        return []
    
    # Look for 2-4 word phrases that appear more than once
    words = text.split()
    repeated = []
    
    for phrase_len in [2, 3, 4]:
        for i in range(len(words) - phrase_len + 1):
            phrase = ' '.join(words[i:i+phrase_len])
            
            # Skip if too short or has common words only
            if len(phrase) < 6:
                continue
            
            # Count occurrences
            count = text.count(phrase)
            if count >= 2 and phrase not in repeated:
                repeated.append(phrase)
    
    return repeated[:5]  # Limit to top 5


def _extract_keywords(text):
    """Extract ticker symbols and meme keywords from text"""
    if not text:
        return []
    
    keywords = []
    
    text_clean = _clean_html(text)
    
    # Look for ticker symbols
    ticker_pattern = r'\$[A-Z]{2,10}\b'
    tickers = re.findall(ticker_pattern, text_clean)
    keywords.extend(tickers)
    
    # Meme-specific keywords that indicate memecoin potential
    meme_keywords = ['moon', 'gem', 'rocket', 'lambo', 'wen', 'hodl', 'diamond', 'hands', 'pump', 
                     'meme', 'doge', 'pepe', 'wojak', 'chad', 'based', 'kek', 'cope', 'seethe',
                     'ape', 'fomo', 'cope', 'bag', 'moon', 'ser', 'fren', 'wagmi', 'ngmi']
    text_lower = text_clean.lower()
    
    for keyword in meme_keywords:
        if keyword in text_lower:
            keywords.append(keyword)
    
    return list(set(keywords))

def _is_meme_related(text):
    """Check if thread is actually about memes/memecoins, not just generic crypto"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # HARD EXCLUDE - if any of these are present, it's NOT a meme
    hard_excludes = [
        'precious metal', 'pmg/', '/pmg', 'gold', 'silver', 'platinum',
        'opened a long', 'opened a short', 'long on btc', 'short on btc',
        'futures', 'options contract', 'forex', 'stock market', 'etf',
        'inflation rate', 'interest rate', 'fed meeting', 'treasury',
        'real estate', 'commodities', 'bonds'
    ]
    
    for exclude in hard_excludes:
        if exclude in text_lower:
            return False
    
    # REQUIRE at least TWO strong meme indicators (not just one generic term)
    strong_meme_indicators = [
        'memecoin', 'meme coin', 'shitcoin',
        'doge', 'pepe', 'shib', 'floki', 'bonk',
        'wojak', 'chad', 'cope', 'seethe', 'kek',
        'wagmi', 'ngmi', 'ser', 'fren', 'wen moon',
        'new launch', 'fair launch', 'stealth launch',
        'ape into', 'to the moon', '100x gem',
        'next doge', 'next pepe', 'pump fun'
    ]
    
    matches = sum(1 for indicator in strong_meme_indicators if indicator in text_lower)
    
    # Need at least 2 strong meme indicators, OR explicit ticker symbol + one meme term
    if matches >= 2:
        return True
    
    # Check for ticker symbol pattern with memecoin context
    has_ticker = bool(re.search(r'\$[A-Z]{2,10}\b', text))
    if has_ticker and matches >= 1:
        return True
    
    return False


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
