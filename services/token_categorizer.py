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
        list: List of category names (up to 3 categories from CATEGORIES)
    """
    
    # Build the prompt
    prompt = f"""You are categorizing a memecoin. Based on the name, symbol, and description, pick up to 3 categories that best fit.

Token Name: {name}
Symbol: ${symbol}
Description: {description[:300] if description else 'N/A'}

Available Categories:
- Animals (dogs, cats, frogs, wildlife, pets, creatures, ALL animal breeds/species)
- Holidays (Halloween, Christmas, Easter, seasonal, spooky, festive)
- Tech (AI, robots, cyberpunk, space, sci-fi, technology, futuristic)
- Finance (ONLY for: banks, stocks, Wall Street, vaults, DeFi, yield, savings, actual financial products - NOT for generic "gains", "wealth", "market" mentions)
- PopCulture (ONLY for SPECIFIC cultural references: famous memes like Grumpy Cat/NPC, real celebrities like Bezos/Trump/Sheen, specific movies/shows like LOTR/Ghibli/Mad Max, actual game franchises. NOT for generic robots/ghosts/fantasy themes)
- Food (food, drinks, restaurants, cooking, edibles)
- Sports (sports, athletics, teams, competitions, games)
- Nature (nature, environment, plants, weather, earth)
- Abstract (philosophy, concepts, ideas, spirituality, mystical)
- Community (general community, social, people)

CRITICAL RULES:
- Animals: ULTIMATE RECOGNITION - Include "Animals" for ANY animal reference including:
  * Generic animals: dog, cat, frog, wolf, fox, bear, bull, owl, eagle, hawk, lion, tiger, penguin, etc.
  * Dog breeds: Jack Russell, Shiba Inu, Corgi, Husky, Bulldog, Poodle, Chihuahua, Golden Retriever, etc.
  * Cat breeds: Persian, Siamese, Maine Coon, Ragdoll, etc.
  * Bird species: Hawk, Eagle, Falcon, Owl, Parrot, Crow, Raven, Robin, etc.
  * Marine life: Dolphin, Whale, Shark, Fish, Octopus, Crab, etc.
  * Reptiles/Amphibians: Gecko, Lizard, Snake, Turtle, Frog, Salamander, etc.
  * Insects: Bee, Butterfly, Ant, Spider, etc.
  * Farm animals: Cow, Pig, Chicken, Horse, Sheep, Goat, etc.
  * Wildlife: Elephant, Giraffe, Zebra, Rhino, Hippo, Kangaroo, etc.
  * Mythical creatures with animal traits: Dragon, Griffin, Phoenix (if animal-focused)
- Holidays: If token has Halloween/holiday themes (ghost, pumpkin, haunted, spooky, zombie, santa), ALWAYS include "Holidays"
- Finance: EXTREMELY RESTRICTIVE - Only use if token is EXPLICITLY a financial product/service (crypto vault, banking service, stock platform, DeFi protocol, lending/yield platform). DO NOT use Finance if token merely mentions "financial freedom", "market", "economy", "gains", "wealth" in its theme
- PopCulture: EXTREMELY RESTRICTIVE - Only use if token directly references a SPECIFIC, IDENTIFIABLE piece of pop culture (Grumpy Cat meme, Jeff Bezos, Donald Trump, Lord of the Rings, Studio Ghibli, Charlie Sheen, Mad Max, NPC meme, etc.). DO NOT use for generic robots, ghosts, fantasy creatures, or vague sci-fi themes - those belong in Tech or Abstract

Respond with a JSON array of 1-3 category names, ordered by relevance.
Example: ["Animals", "Holidays"] or ["Tech", "Finance"] or ["Community"]"""

    try:
        api_token = os.environ.get('OPENROUTER')
        if not api_token:
            logger.warning("OPENROUTER API key not found, using default category")
            return ['Community']
        
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
                    {'role': 'system', 'content': 'You are a token categorization assistant. Respond with ONLY a JSON array of category names.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,  # Slightly higher for variety
                'max_tokens': 50
            },
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        response_text = result['choices'][0]['message']['content'].strip()
        
        # Parse JSON response
        try:
            categories = json.loads(response_text)
            if not isinstance(categories, list):
                categories = [categories]
        except json.JSONDecodeError:
            # Try to extract categories from plain text
            categories = [cat.strip() for cat in response_text.replace('[', '').replace(']', '').replace('"', '').split(',')]
        
        # Validate and filter categories
        valid_categories = []
        for category in categories:
            category = category.strip()
            if category in CATEGORIES:
                valid_categories.append(category)
            else:
                # Try fuzzy match
                category_lower = category.lower()
                for valid_category in CATEGORIES:
                    if valid_category.lower() in category_lower or category_lower in valid_category.lower():
                        if valid_category not in valid_categories:
                            valid_categories.append(valid_category)
                        break
        
        # Ensure we have at least one category
        if not valid_categories:
            valid_categories = ['Community']
        
        # Limit to 3 categories
        valid_categories = valid_categories[:3]
        
        logger.info(f"Categorized token {symbol} as: {valid_categories}")
        return valid_categories
        
    except Exception as e:
        logger.error(f"Error categorizing token {symbol}: {e}")
        return ['Community']

def categorize_token_with_fallback(name, symbol, description=''):
    """
    Categorize token with keyword-based fallback if AI fails.
    
    This provides a backup categorization method using simple keyword matching
    when the AI API is unavailable or fails.
    
    Returns:
        list: List of category names (up to 3)
    """
    
    # Try AI categorization first
    categories = categorize_token(name, symbol, description)
    
    # If AI only returned Community, try keyword-based fallback
    if categories == ['Community']:
        combined_text = f"{name} {symbol} {description}".lower()
        fallback_categories = []
        
        # Keyword-based categorization (can match multiple)
        # ULTIMATE animal recognition - comprehensive list of breeds, species, and animal terms
        animal_keywords = [
            # Generic animals
            'dog', 'cat', 'frog', 'animal', 'pet', 'paw', 'puppy', 'kitten', 'wolf', 'fox', 'bear', 
            'tiger', 'lion', 'monkey', 'penguin', 'owl', 'eagle', 'hawk', 'creature', 'beast', 'bull',
            # Dog breeds
            'shiba', 'shiba inu', 'jack russell', 'russell', 'corgi', 'husky', 'bulldog', 'poodle', 
            'chihuahua', 'retriever', 'golden retriever', 'labrador', 'dachshund', 'beagle', 'pug', 
            'doberman', 'rottweiler', 'german shepherd', 'dalmatian', 'greyhound', 'mastiff', 'terrier',
            # Cat breeds
            'persian', 'siamese', 'maine coon', 'ragdoll', 'bengal', 'sphynx', 'tabby',
            # Birds
            'hawk', 'eagle', 'falcon', 'raven', 'crow', 'parrot', 'robin', 'sparrow', 'pigeon', 
            'dove', 'hummingbird', 'woodpecker', 'flamingo', 'peacock', 'swan', 'duck', 'goose',
            'chicken', 'rooster', 'hen', 'turkey', 'ostrich', 'emu', 'pelican', 'seagull',
            # Marine life
            'dolphin', 'whale', 'shark', 'fish', 'octopus', 'squid', 'crab', 'lobster', 'shrimp',
            'seal', 'walrus', 'otter', 'turtle', 'tortoise', 'seahorse', 'jellyfish', 'starfish',
            'clownfish', 'goldfish', 'salmon', 'tuna', 'barracuda', 'manta', 'stingray', 'krab',
            # Reptiles & Amphibians
            'gecko', 'lizard', 'snake', 'python', 'cobra', 'viper', 'iguana', 'chameleon', 
            'salamander', 'newt', 'crocodile', 'alligator', 'komodo',
            # Insects & Arachnids
            'bee', 'butterfly', 'ant', 'spider', 'beetle', 'ladybug', 'dragonfly', 'mosquito',
            'moth', 'wasp', 'hornet', 'scorpion', 'tarantula', 'mantis',
            # Farm animals
            'cow', 'pig', 'horse', 'sheep', 'goat', 'donkey', 'mule', 'llama', 'alpaca',
            # Wildlife & Exotic
            'elephant', 'giraffe', 'zebra', 'rhino', 'rhinoceros', 'hippo', 'hippopotamus', 
            'kangaroo', 'koala', 'panda', 'gorilla', 'chimpanzee', 'orangutan', 'lemur', 
            'sloth', 'raccoon', 'badger', 'weasel', 'ferret', 'hamster', 'rabbit', 'bunny',
            'squirrel', 'chipmunk', 'deer', 'elk', 'moose', 'reindeer', 'antelope', 'gazelle',
            'leopard', 'cheetah', 'jaguar', 'panther', 'lynx', 'cougar', 'puma', 'hyena',
            'armadillo', 'anteater', 'platypus', 'hedgehog', 'porcupine', 'beaver', 'mole',
            'bat', 'rat', 'mouse', 'mice', 'gerbil', 'chinchilla', 'guinea pig',
            # Mythical/Fantasy animals
            'dragon', 'phoenix', 'griffin', 'chimera', 'unicorn', 'pegasus', 'kraken',
            # Animal-related terms
            'fur', 'feather', 'scales', 'tail', 'whiskers', 'claws', 'fangs', 'horns',
            'hoof', 'hooves', 'mane', 'trunk', 'snout', 'beak', 'wing', 'fins'
        ]
        if any(word in combined_text for word in animal_keywords):
            fallback_categories.append('Animals')
        if any(word in combined_text for word in ['halloween', 'christmas', 'easter', 'holiday', 'santa', 'pumpkin', 'ghost', 'haunt', 'spooky', 'scary', 'festive', 'seasonal', 'zombie', 'undead']):
            fallback_categories.append('Holidays')
        if any(word in combined_text for word in ['ai', 'robot', 'cyber', 'space', 'tech', 'sci-fi', 'alien', 'future', 'digital', 'virtual', 'quantum', 'blockchain', 'forge', 'clockwork']):
            fallback_categories.append('Tech')
        # Finance: VERY restrictive - only actual finance products
        if any(word in combined_text for word in ['vault', 'bank', 'stock', 'wall street', 'defi', 'yield', 'savings', 'staking', 'lending']):
            fallback_categories.append('Finance')
        # PopCulture: Very restrictive - only specific cultural references
        if any(word in combined_text for word in ['grumpy cat', 'bezos', 'trump', 'sheen', 'ghibli', 'lotr', 'lord of the rings', 'mad max', 'npc', 'samurai', 'ronin']):
            fallback_categories.append('PopCulture')
        if any(word in combined_text for word in ['food', 'drink', 'pizza', 'burger', 'coffee', 'restaurant', 'meal', 'snack', 'beverage', 'crunch', 'flavor']):
            fallback_categories.append('Food')
        if any(word in combined_text for word in ['sport', 'football', 'basketball', 'soccer', 'team', 'athlete', 'competition', 'championship', 'race', 'racing']):
            fallback_categories.append('Sports')
        if any(word in combined_text for word in ['nature', 'tree', 'forest', 'ocean', 'environment', 'green', 'earth', 'plant', 'leaf', 'acorn', 'nut']):
            fallback_categories.append('Nature')
        if any(word in combined_text for word in ['philosophy', 'mind', 'soul', 'spirit', 'abstract', 'concept', 'mystic', 'mystical', 'ancient', 'shadows', 'darkness']):
            fallback_categories.append('Abstract')
        
        if fallback_categories:
            return fallback_categories[:3]  # Limit to 3
    
    return categories
