"""
Check Oracle Address Configuration  
Verify what oracle address is configured in GraduationController contract
"""

from services.web3_service import get_web3_service

def main():
    w3_service = get_web3_service()
    
    print("=" * 80)
    print("ORACLE ADDRESS VERIFICATION")
    print("=" * 80)
    print()
    
    # Get GraduationController contract
    grad_controller = w3_service.contracts['GraduationController']
    
    # Call graduationOracle() view function (it's a public variable)
    try:
        oracle_address = grad_controller.functions.graduationOracle().call()
        print(f"✅ Oracle address from contract: {oracle_address}")
    except Exception as e:
        print(f"❌ Failed to get oracle address: {str(e)}")
        oracle_address = None
    
    # Compare with what we're using
    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print(f"Contract oracle:      {oracle_address}")
    print(f"Using in code:        {w3_service.oracle_account.address}")
    print(f"Deployer address:     {w3_service.deployer_account.address}")
    print()
    
    if oracle_address and oracle_address.lower() == w3_service.oracle_account.address.lower():
        print("✅ MATCH: Oracle addresses match!")
    elif oracle_address and oracle_address.lower() == w3_service.deployer_account.address.lower():
        print("⚠️ ISSUE: Contract oracle is set to DEPLOYER, not derived oracle!")
        print("   This explains the 'Only oracle can initiate' error")
    else:
        print("❌ MISMATCH: Oracle addresses do not match!")
        print("   This explains the 'Only oracle can initiate' error")
    
    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if oracle_address and oracle_address.lower() != w3_service.oracle_account.address.lower():
        print("To fix this issue:")
        print(f"1. The contract oracle is set to: {oracle_address}")
        print(f"2. The code is using: {w3_service.oracle_account.address}")
        print()
        print("Options:")
        print("A. Update contract: Call setGraduationOracle() to change to derived oracle")
        print(f"   Command: setGraduationOracle('{w3_service.oracle_account.address}')")
        print(f"B. Use correct wallet: Use {oracle_address} for graduation calls")
    
if __name__ == "__main__":
    main()
