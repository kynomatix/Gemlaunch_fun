"""
Hide V1 test tokens from marketplace

These tokens were deployed during V1 era and cannot graduate.
Hiding them cleans up the UI for V2 testing.
Data is preserved for historical reference.
"""
import sys
sys.path.insert(0, '/home/runner/workspace')

from app import app, db
from models import Token

# V1 test tokens that should be hidden
V1_TEST_TOKENS = [
    'KPAN', 'RAGR', 'SPK', 'KTAR', 'PKN', 'PXLS', 
    'KA', 'GRUMP', 'PWN', 'ZZING', 'JAK', 'KWAL', 'DUMP', 'KASB'
]

with app.app_context():
    print("V1 TOKEN CLEANUP")
    print("=" * 70)
    print()
    
    # Find all V1 tokens
    v1_tokens = Token.query.filter(Token.symbol.in_(V1_TEST_TOKENS)).all()
    
    print(f"Found {len(v1_tokens)} V1 test tokens")
    print()
    
    # Hide visible ones
    hidden_count = 0
    for token in v1_tokens:
        status = "visible" if token.is_visible else "hidden"
        print(f"  {token.symbol:8} (ID {token.id:3}) - {status}")
        
        if token.is_visible:
            token.is_visible = False
            hidden_count += 1
    
    if hidden_count > 0:
        db.session.commit()
        print()
        print(f"✅ Hid {hidden_count} tokens from marketplace")
    else:
        print()
        print("✅ All V1 tokens already hidden")
    
    print()
    print("Result:")
    print("  - V1 tokens hidden from UI")
    print("  - Data preserved in database")
    print("  - Marketplace shows only working tokens")
    print("  - Ready for V2 testing")
