"""
Kaspa technical knowledge base for Gemmy Zeroday Memification Engine
Provides Kaspa-specific tech concepts and memeable variations
"""

KASPA_TECH_CONCEPTS = {
    'technical_terms': {
        'GHOSTDAG': {
            'description': 'The DAG ordering algorithm that allows parallel blocks',
            'memeable_variations': ['SpookyCoin', 'GhostBlocks', 'PhantomChain', 'SpectralDAG'],
            'meme_potential': 'high',
            'keywords': ['ghost', 'spooky', 'phantom', 'spectral']
        },
        'DAGKnight': {
            'description': 'Advanced consensus protocol for Kaspa',
            'memeable_variations': ['KnightRider', 'DAGLord', 'BlockKnight', 'ChainKnight'],
            'meme_potential': 'high',
            'keywords': ['knight', 'armor', 'sword', 'medieval']
        },
        'BlockDAG': {
            'description': 'Directed Acyclic Graph of blocks instead of linear chain',
            'memeable_variations': ['DAGMoon', 'SuperDAG', 'MegaDAG', 'TurboDAG'],
            'meme_potential': 'medium',
            'keywords': ['dag', 'graph', 'network', 'web']
        },
        '10 BPS': {
            'description': '10 blocks per second - ultra-fast block creation',
            'memeable_variations': ['TenSpeed', 'HyperSpeed', 'RocketBlocks', 'SpeedDemon'],
            'meme_potential': 'very_high',
            'keywords': ['fast', 'speed', 'lightning', 'rocket', 'turbo']
        },
        'Phantom Blocks': {
            'description': 'Blocks that exist but are not in the main chain',
            'memeable_variations': ['PhantomMoon', 'GhostBlocks', 'InvisibleGains', 'ShadowChain'],
            'meme_potential': 'high',
            'keywords': ['phantom', 'ghost', 'invisible', 'shadow']
        },
        'Parallel Processing': {
            'description': 'Multiple blocks processed simultaneously',
            'memeable_variations': ['MultiMoon', 'ParallelGains', 'SimultaneousLambo', 'HyperThreaded'],
            'meme_potential': 'medium',
            'keywords': ['parallel', 'multi', 'simultaneous', 'concurrent']
        },
        'Proof of Work': {
            'description': 'Kaspa uses GPU-friendly PoW mining',
            'memeable_variations': ['WorkHard', 'GPUGrinder', 'MiningMoon', 'HashHero'],
            'meme_potential': 'medium',
            'keywords': ['mining', 'work', 'hash', 'gpu']
        },
        'kHeavyHash': {
            'description': 'Kaspa\'s custom hashing algorithm',
            'memeable_variations': ['HeavyMetal', 'MassiveHash', 'WeightLifter', 'IronHash'],
            'meme_potential': 'high',
            'keywords': ['heavy', 'hash', 'weight', 'massive']
        },
        'Instant Confirmations': {
            'description': 'Near-instant transaction finality',
            'memeable_variations': ['InstaMoon', 'QuickGains', 'FlashFinance', 'ZeroWait'],
            'meme_potential': 'very_high',
            'keywords': ['instant', 'fast', 'quick', 'immediate', 'flash']
        },
        'Rust Implementation': {
            'description': 'Kaspa core written in Rust for performance',
            'memeable_variations': ['RustRocket', 'OxidizedGains', 'IronCode', 'RustyMoon'],
            'meme_potential': 'low',
            'keywords': ['rust', 'iron', 'metal', 'oxidized']
        }
    },
    
    'community_memes': {
        'kaspa_green': {
            'description': 'The iconic Kaspa green color',
            'variations': ['GreenMachine', 'EmeraldMoon', 'GreenGains'],
            'hex_color': '#70C7BA'
        },
        'kaspa_blue': {
            'description': 'Kaspa brand blue',
            'variations': ['BlueRocket', 'SapphireMoon', 'BlueChip'],
            'hex_color': '#2A9D8F'
        },
        'faster_than_light': {
            'description': 'Kaspa\'s legendary speed narrative',
            'variations': ['WarpSpeed', 'Lightspeed', 'HyperDrive', 'Sonic']
        },
        'blockdag_not_blockchain': {
            'description': 'The key differentiator',
            'variations': ['DAGGang', 'NotYourChain', 'NextGenDAG']
        }
    },
    
    'trending_patterns': {
        'combine_concepts': [
            'Combine tech terms with meme culture (e.g., GHOSTDAG + Pepe = SpookyPepe)',
            'Mix speed narrative with wealth memes (e.g., 10 BPS + Lambo = TenSpeedLambo)',
            'Blend Kaspa colors with animals (e.g., Green + Dog = GreenDoge)'
        ],
        'suffix_strategies': [
            'Add "Kas" prefix (e.g., KasRocket, KasMoon, KasGem)',
            'Add "DAG" suffix (e.g., SpeedDAG, MoonDAG, RocketDAG)',
            'Use "10" for speed (e.g., 10XSpeed, Ten2Moon)'
        ]
    }
}


def get_kaspa_meme_suggestions(include_technical=True, include_community=True, limit=20):
    """
    Get Kaspa-based meme coin suggestions
    
    Args:
        include_technical (bool): Include technical concept variations
        include_community (bool): Include community meme variations
        limit (int): Maximum number of suggestions to return
        
    Returns:
        list: List of meme suggestions with structure:
            {
                'name': str,
                'concept': str,
                'category': str,  # 'technical' or 'community'
                'meme_potential': str,  # 'low', 'medium', 'high', 'very_high'
                'keywords': list
            }
    """
    suggestions = []
    
    if include_technical:
        for tech_name, tech_data in KASPA_TECH_CONCEPTS['technical_terms'].items():
            for variation in tech_data['memeable_variations']:
                ticker = variation.upper()[:5] if len(variation) <= 5 else variation.upper()[:4]
                suggestions.append({
                    'name': variation,
                    'concept': tech_data['description'],
                    'category': 'technical',
                    'meme_potential': tech_data['meme_potential'],
                    'keywords': tech_data['keywords'],
                    'ticker_suggestion': ticker
                })
    
    if include_community:
        for meme_name, meme_data in KASPA_TECH_CONCEPTS['community_memes'].items():
            for variation in meme_data.get('variations', []):
                ticker = variation.upper()[:5] if len(variation) <= 5 else variation.upper()[:4]
                suggestions.append({
                    'name': variation,
                    'concept': meme_data['description'],
                    'category': 'community',
                    'meme_potential': 'medium',
                    'keywords': [variation.lower()],
                    'ticker_suggestion': ticker
                })
    
    suggestions.sort(key=lambda x: {
        'very_high': 4,
        'high': 3,
        'medium': 2,
        'low': 1
    }.get(x['meme_potential'], 0), reverse=True)
    
    return suggestions[:limit]


def get_kaspa_ticker_suggestions(base_word):
    """
    Generate ticker symbol suggestions based on Kaspa concepts
    
    Args:
        base_word (str): Base word to generate variations from
        
    Returns:
        list: List of ticker suggestions
    """
    base_upper = base_word.upper()
    
    suggestions = [
        f"KAS{base_upper[:4]}",
        f"{base_upper[:4]}KAS",
        f"10{base_upper[:3]}",
        f"{base_upper[:3]}DAG",
        f"GHOST{base_upper[:2]}",
        f"{base_upper[:5]}K"
    ]
    
    suggestions = [s[:8] for s in suggestions]
    
    return list(set(suggestions))


def analyze_meme_kaspa_relevance(meme_data):
    """
    Analyze how well a meme concept fits with Kaspa branding
    
    Args:
        meme_data (dict): Meme data with 'title' and 'keywords'
        
    Returns:
        dict: Relevance score and suggestions
            {
                'relevance_score': float,  # 0.0 to 1.0
                'matching_concepts': list,
                'suggested_adaptations': list
            }
    """
    title = meme_data.get('title', '').lower()
    keywords = [k.lower() for k in meme_data.get('keywords', [])]
    full_text = f"{title} {' '.join(keywords)}"
    
    matching_concepts = []
    relevance_score = 0.0
    
    for tech_name, tech_data in KASPA_TECH_CONCEPTS['technical_terms'].items():
        tech_keywords = tech_data['keywords']
        matches = sum(1 for kw in tech_keywords if kw in full_text)
        
        if matches > 0:
            matching_concepts.append({
                'concept': tech_name,
                'variations': tech_data['memeable_variations']
            })
            relevance_score += matches * 0.2
    
    for meme_name, meme_data in KASPA_TECH_CONCEPTS['community_memes'].items():
        if meme_name.replace('_', ' ') in full_text:
            matching_concepts.append({
                'concept': meme_name,
                'variations': meme_data.get('variations', [])
            })
            relevance_score += 0.3
    
    kaspa_terms = ['kaspa', 'kas', 'dag', 'ghost', 'phantom', 'speed', 'fast', 'green', 'blue']
    kaspa_mentions = sum(1 for term in kaspa_terms if term in full_text)
    relevance_score += kaspa_mentions * 0.1
    
    relevance_score = min(relevance_score, 1.0)
    
    suggested_adaptations = []
    if matching_concepts:
        for concept in matching_concepts[:3]:
            suggested_adaptations.extend(concept['variations'][:2])
    
    return {
        'relevance_score': round(relevance_score, 2),
        'matching_concepts': matching_concepts,
        'suggested_adaptations': suggested_adaptations[:5]
    }
