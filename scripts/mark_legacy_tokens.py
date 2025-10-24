"""
Mark Legacy V1 Tokens as Graduation-Disabled

This script identifies tokens deployed with the old V1 GraduationController
and marks them with graduation_disabled=True to prevent graduation attempts
while keeping them visible in the marketplace.

V1 GraduationController: 0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e (DEPRECATED)
V2 GraduationController: 0x147e3ecbe189bb301175001706ff1f44df33b3ab (CURRENT)
"""

import sys
import logging
from app import app, db, Token
from services.web3_service import Web3Service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# V1 GraduationController address (deprecated)
V1_CONTROLLER = "0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e"
V2_CONTROLLER = "0x147e3ecbe189bb301175001706ff1f44df33b3ab"

def mark_legacy_tokens():
    """Mark all V1 tokens as graduation_disabled"""
    
    w3s = Web3Service()
    
    with app.app_context():
        tokens = Token.query.all()
        
        v1_tokens = []
        v2_tokens = []
        error_tokens = []
        
        print("=" * 70)
        print("SCANNING TOKENS FOR LEGACY V1 GRADUATION CONTROLLER")
        print("=" * 70)
        
        for token in tokens:
            try:
                # Check which GraduationController this token uses
                pool = w3s.get_bonding_pool_contract(token.contract_address)
                gc_address = pool.functions.graduationController().call()
                
                if gc_address.lower() == V1_CONTROLLER.lower():
                    v1_tokens.append(token)
                    status = "LEGACY V1"
                    print(f"🔴 {status:12} | {token.symbol:10} | {token.name[:40]}")
                elif gc_address.lower() == V2_CONTROLLER.lower():
                    v2_tokens.append(token)
                    status = "V2 CURRENT"
                    print(f"🟢 {status:12} | {token.symbol:10} | {token.name[:40]}")
                else:
                    # Unknown controller
                    error_tokens.append((token, f"Unknown controller: {gc_address}"))
                    print(f"⚠️  UNKNOWN     | {token.symbol:10} | Controller: {gc_address}")
                    
            except Exception as e:
                error_tokens.append((token, str(e)))
                print(f"❌ ERROR       | {token.symbol:10} | {str(e)[:40]}")
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total tokens scanned:  {len(tokens)}")
        print(f"  V2 tokens (current): {len(v2_tokens)}")
        print(f"  V1 tokens (legacy):  {len(v1_tokens)}")
        print(f"  Errors/Unknown:      {len(error_tokens)}")
        
        if v1_tokens:
            print("\n" + "=" * 70)
            print("MARKING V1 TOKENS AS GRADUATION-DISABLED")
            print("=" * 70)
            
            for token in v1_tokens:
                token.graduation_disabled = True
                token.graduation_status = 'active'  # Reset to active (won't trigger graduation)
                print(f"✅ Marked {token.symbol} as graduation_disabled")
            
            db.session.commit()
            print(f"\n✅ Successfully marked {len(v1_tokens)} legacy tokens as graduation-disabled")
            print("   These tokens remain visible but will not attempt graduation")
        else:
            print("\n✅ No legacy V1 tokens found - all tokens are using V2 controller")
        
        if error_tokens:
            print("\n" + "=" * 70)
            print("ERRORS")
            print("=" * 70)
            for token, error in error_tokens:
                print(f"❌ {token.symbol}: {error}")

if __name__ == '__main__':
    mark_legacy_tokens()
