"""
Know Your Meme scraper for Gemmy Zeroday Memification Engine
Scrapes Know Your Meme for trending and new memes BEFORE they become coins
"""

import re
import time
from datetime import datetime, timedelta, timezone
import logging

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


ESTABLISHED_MEMES = {
    'pepe', 'doge', 'dogecoin', 'shiba inu', 'wojak', 'chad', 'gigachad',
    'trollface', 'rickroll', 'grumpy cat', 'bad luck brian', 'scumbag steve',
    'success kid', 'distracted boyfriend', 'hide the pain harold', 'stonks',
    'big chungus', 'ugandan knuckles', 'salt bae', 'overly attached girlfriend',
    'yao ming', 'disaster girl', 'first world problems', 'philosoraptor',
    'boromir', 'one does not simply', 'x all the y', 'all your base',
    'lolcats', 'ermahgerd', 'nyan cat', 'forever alone', 'rage comics',
    'y u no', 'fuuuu', 'me gusta', 'not sure if', 'bad joke eel'
}


def scrape_knowyourmeme():
    """
    Scrape Know Your Meme for trending and recently added memes
    
    Returns:
        list: List of meme dictionaries with structure:
            {
                'title': str,
                'description': str,
                'tags': list,
                'status': str,  # 'new', 'trending', etc.
                'added_date': datetime,
                'source': 'knowyourmeme',
                'url': str
            }
    """
    if requests is None:
        logger.warning("requests library not available, returning empty list")
        return []
    
    if BeautifulSoup is None:
        logger.warning("BeautifulSoup not available, returning empty list")
        return []
    
    all_memes = []
    
    trending_memes = _scrape_trending_page()
    all_memes.extend(trending_memes)
    
    time.sleep(2)
    
    recent_memes = _scrape_recent_page()
    all_memes.extend(recent_memes)
    
    all_memes = _deduplicate_memes(all_memes)
    
    all_memes = _filter_memes(all_memes)
    
    all_memes.sort(key=lambda x: x['added_date'], reverse=True)
    
    logger.info(f"Scraped {len(all_memes)} qualifying memes from Know Your Meme")
    return all_memes[:50]


def _scrape_trending_page():
    """Scrape Know Your Meme main page for popular memes"""
    try:
        url = "https://knowyourmeme.com/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        memes = []
        
        popular_section = soup.find(text=re.compile('Popular right now', re.I))
        if popular_section:
            parent = popular_section.find_parent()
            if parent:
                links = parent.find_next_siblings() if parent else []
                for sibling in links[:20]:
                    meme_links = sibling.find_all('a', href=re.compile(r'/memes/'))
                    for link in meme_links[:10]:
                        meme_data = _extract_from_link(link, status='trending')
                        if meme_data:
                            memes.append(meme_data)
        
        all_meme_links = soup.find_all('a', href=re.compile(r'/memes/[^/]+$'))
        for link in all_meme_links[:30]:
            if not any(m['url'] == link.get('href', '') for m in memes):
                meme_data = _extract_from_link(link, status='popular')
                if meme_data:
                    memes.append(meme_data)
        
        logger.info(f"Scraped {len(memes)} memes from main page")
        return memes
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping Know Your Meme main page: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in _scrape_trending_page: {e}")
        return []


def _scrape_recent_page():
    """Scrape Know Your Meme main page for fresh entries"""
    try:
        url = "https://knowyourmeme.com/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        memes = []
        
        fresh_section = soup.find(text=re.compile('Fresh Entries', re.I))
        if fresh_section:
            parent = fresh_section.find_parent()
            if parent:
                links = parent.find_next_siblings() if parent else []
                for sibling in links[:20]:
                    meme_links = sibling.find_all('a', href=re.compile(r'/memes/'))
                    for link in meme_links[:10]:
                        meme_data = _extract_from_link(link, status='new')
                        if meme_data:
                            memes.append(meme_data)
        
        logger.info(f"Scraped {len(memes)} memes from fresh entries")
        return memes
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping Know Your Meme fresh entries: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in _scrape_recent_page: {e}")
        return []


def _extract_from_link(link_element, status='trending'):
    """Extract meme data from a link element"""
    try:
        title = link_element.get_text(strip=True)
        if not title or len(title) < 3:
            return None
        
        meme_url = link_element.get('href', '')
        if not meme_url or '/memes/' not in meme_url:
            return None
            
        if not meme_url.startswith('http'):
            meme_url = f"https://knowyourmeme.com{meme_url}"
        
        parent = link_element.find_parent()
        description = ""
        if parent:
            desc_text = parent.get_text(strip=True)
            if desc_text and desc_text != title:
                description = desc_text[:300]
        
        tags = []
        
        date_match = re.search(r'(\d+)\s+(hour|day|week|month)s?\s+ago', parent.get_text() if parent else '')
        added_date = datetime.now(timezone.utc)
        if date_match:
            parsed_date = _parse_date(date_match.group(0))
            if parsed_date:
                added_date = parsed_date
        
        return {
            'title': title,
            'description': description,
            'tags': tags,
            'status': status,
            'added_date': added_date,
            'source': 'knowyourmeme',
            'url': meme_url
        }
        
    except Exception as e:
        logger.debug(f"Error extracting from link: {e}")
        return None


def _get_description_from_detail_page(url):
    """Fetch description from meme detail page (with rate limiting)"""
    try:
        time.sleep(1)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        about_section = soup.find(['section', 'div'], class_=lambda x: x and 'about' in str(x).lower())
        if about_section:
            paragraphs = about_section.find_all('p', limit=2)
            if paragraphs:
                return ' '.join(p.get_text(strip=True) for p in paragraphs)
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')
        
        first_para = soup.find('p')
        if first_para:
            return first_para.get_text(strip=True)
        
        return ""
        
    except Exception as e:
        logger.debug(f"Error fetching description from {url}: {e}")
        return ""


def _extract_tags(element):
    """Extract tags/categories from element"""
    tags = []
    
    tag_elements = element.find_all(['span', 'a'], class_=lambda x: x and any(
        cls in str(x).lower() for cls in ['tag', 'category', 'label']
    ))
    
    for tag_elem in tag_elements:
        tag_text = tag_elem.get_text(strip=True)
        if tag_text and len(tag_text) < 30:
            tags.append(tag_text)
    
    return tags[:10]


def _parse_date(date_text):
    """Parse date from various text formats"""
    if not date_text:
        return None
    
    try:
        date_text = date_text.lower().strip()
        
        time_ago_patterns = [
            (r'(\d+)\s*hour', lambda h: datetime.now(timezone.utc) - timedelta(hours=int(h))),
            (r'(\d+)\s*day', lambda d: datetime.now(timezone.utc) - timedelta(days=int(d))),
            (r'(\d+)\s*week', lambda w: datetime.now(timezone.utc) - timedelta(weeks=int(w))),
            (r'(\d+)\s*month', lambda m: datetime.now(timezone.utc) - timedelta(days=int(m)*30)),
        ]
        
        for pattern, delta_func in time_ago_patterns:
            match = re.search(pattern, date_text)
            if match:
                return delta_func(match.group(1))
        
        if 'today' in date_text or 'just now' in date_text:
            return datetime.now(timezone.utc)
        
        if 'yesterday' in date_text:
            return datetime.now(timezone.utc) - timedelta(days=1)
        
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_text, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error parsing date '{date_text}': {e}")
        return None


def _deduplicate_memes(memes):
    """Remove duplicate memes based on URL"""
    seen_urls = set()
    unique_memes = []
    
    for meme in memes:
        if meme['url'] not in seen_urls:
            seen_urls.add(meme['url'])
            unique_memes.append(meme)
    
    return unique_memes


def _filter_memes(memes):
    """Filter memes based on criteria: recent, not established classics"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
    
    filtered = []
    
    for meme in memes:
        if meme['added_date'] < cutoff_date:
            continue
        
        title_lower = meme['title'].lower()
        description_lower = meme['description'].lower()
        
        is_established = False
        for established in ESTABLISHED_MEMES:
            if established in title_lower or established in description_lower:
                is_established = True
                break
        
        if is_established:
            logger.debug(f"Filtered out established meme: {meme['title']}")
            continue
        
        has_crypto_potential = _check_crypto_potential(meme)
        if has_crypto_potential:
            filtered.append(meme)
    
    return filtered


def _check_crypto_potential(meme):
    """Check if meme has potential to become a crypto token"""
    title_lower = meme['title'].lower()
    description_lower = meme['description'].lower()
    full_text = f"{title_lower} {description_lower}"
    
    positive_signals = [
        'viral', 'trending', 'twitter', 'tiktok', 'meme',
        'character', 'mascot', 'animal', 'coin', 'token',
        'crypto', 'nft', 'internet culture', 'social media',
        'phenomenon', 'popular', 'community', 'frog', 'dog',
        'cat', 'bird', 'bear', 'bull', 'inu', 'elon'
    ]
    
    negative_signals = [
        'politician', 'political', 'election', 'president',
        'controversy', 'scandal', 'tragedy', 'death',
        'war', 'violence', 'offensive', 'racist',
        'adult content', 'nsfw', 'explicit'
    ]
    
    for negative in negative_signals:
        if negative in full_text:
            return False
    
    signal_count = sum(1 for signal in positive_signals if signal in full_text)
    
    if signal_count >= 2:
        return True
    
    has_animal = any(animal in full_text for animal in ['dog', 'cat', 'frog', 'bear', 'bird', 'inu'])
    has_meme = 'meme' in full_text or 'viral' in full_text
    
    if has_animal and has_meme:
        return True
    
    return signal_count >= 1
