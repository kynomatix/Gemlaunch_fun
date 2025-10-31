"""
Token Categorization Service
Automatically categorizes tokens using AI based on name, symbol, and description
"""

import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

# Available categories
CATEGORIES = [
    'Animals',      # dogs, cats, frogs, etc.
    'Holidays',     # Halloween, Christmas, Easter
    'Tech',         # AI, robots, cyberpunk, space, sci-fi
    'Finance',      # money, stocks, banks
    'PopCulture',   # memes, movies, gaming, celebrities
    'Food',         # food and drinks
    'Sports',       # sports and athletics
    'Nature',       # nature, environment
    'Abstract',     # philosophy, concepts
    'Community'     # default/fallback category
]

def categorize_token(name, symbol, description=''):
    """
    Categorize a token using AI based on its metadata.
    
    Args:
        name: Token name
        symbol: Token symbol/ticker
        description: Token description (optional)
    
    Returns:
        str: Category name (one of CATEGORIES)
    """
    
    # Build the prompt
    prompt = f"""You are categorizing a memecoin. Based on the name, symbol, and description, pick ONE category that best fits.

Token Name: {name}
Symbol: ${symbol}
Description: {description[:200] if description else 'N/A'}

Available Categories:
- Animals (dogs, cats, frogs, wildlife, pets)
- Holidays (Halloween, Christmas, Easter, seasonal)
- Tech (AI, robots, cyberpunk, space, sci-fi, technology)
- Finance (money, stocks, banks, wall street, trading)
- PopCulture (memes, movies, gaming, TV, celebrities, internet culture)
- Food (food, drinks, restaurants, cooking)
- Sports (sports, athletics, teams, competitions)
- Nature (nature, environment, plants, weather)
- Abstract (philosophy, concepts, ideas, spirituality)
- Community (general community, social, people)

Respond with ONLY the category name, nothing else. If unsure, choose Community."""

    try:
        api_token = os.environ.get('OPENROUTER')
        if not api_token:
            logger.warning("OPENROUTER API key not found, using default category")
            return 'Community'
        
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://gemlaunch.fun',
                'X-Title': 'Gemlaunch.fun'
            },
            json={
                'model': 'meta-llama/llama-3.1-8b-instruct',  # Cheaper and faster model
                'messages': [
                    {'role': 'system', 'content': 'You are a token categorization assistant. Respond with ONLY the category name.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,  # Low temperature for consistent categorization
                'max_tokens': 20
            },
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        category = result['choices'][0]['message']['content'].strip()
        
        # Validate the category is in our list
        if category in CATEGORIES:
            logger.info(f"Categorized token {symbol} as: {category}")
            return category
        
        # Try to find a partial match
        category_lower = category.lower()
        for valid_category in CATEGORIES:
            if valid_category.lower() in category_lower or category_lower in valid_category.lower():
                logger.info(f"Categorized token {symbol} as: {valid_category} (fuzzy match)")
                return valid_category
        
        # Fallback to Community
        logger.warning(f"AI returned invalid category '{category}' for {symbol}, using Community")
        return 'Community'
        
    except Exception as e:
        logger.error(f"Error categorizing token {symbol}: {e}")
        return 'Community'

def categorize_token_with_fallback(name, symbol, description=''):
    """
    Categorize token with keyword-based fallback if AI fails.
    
    This provides a backup categorization method using simple keyword matching
    when the AI API is unavailable or fails.
    """
    
    # Try AI categorization first
    category = categorize_token(name, symbol, description)
    
    # If AI returned Community, try keyword-based fallback
    if category == 'Community':
        combined_text = f"{name} {symbol} {description}".lower()
        
        # Keyword-based categorization
        if any(word in combined_text for word in ['dog', 'cat', 'frog', 'animal', 'pet', 'paw', 'puppy', 'kitten']):
            return 'Animals'
        elif any(word in combined_text for word in ['halloween', 'christmas', 'easter', 'holiday', 'santa', 'pumpkin']):
            return 'Holidays'
        elif any(word in combined_text for word in ['ai', 'robot', 'cyber', 'space', 'tech', 'sci-fi', 'alien', 'future']):
            return 'Tech'
        elif any(word in combined_text for word in ['money', 'finance', 'stock', 'bank', 'wall street', 'trading', 'cash']):
            return 'Finance'
        elif any(word in combined_text for word in ['meme', 'movie', 'game', 'gaming', 'celebrity', 'pop', 'culture']):
            return 'PopCulture'
        elif any(word in combined_text for word in ['food', 'drink', 'pizza', 'burger', 'coffee', 'restaurant']):
            return 'Food'
        elif any(word in combined_text for word in ['sport', 'football', 'basketball', 'soccer', 'team', 'athlete']):
            return 'Sports'
        elif any(word in combined_text for word in ['nature', 'tree', 'forest', 'ocean', 'environment', 'green']):
            return 'Nature'
        elif any(word in combined_text for word in ['philosophy', 'mind', 'soul', 'spirit', 'abstract', 'concept']):
            return 'Abstract'
    
    return category
