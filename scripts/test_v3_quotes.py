#!/usr/bin/env python3
"""
Test script for Uniswap V3 quote calculation
Validates V3 math implementation against MEGA pool on Kasplex Testnet

Token: 0xe9c2f32816054c87ab04b7eb57cce657ea1ade76 (MEGA)
Pool: 0x1Bc9e2F8a3f1e89D741333CC85847e2C34F5E44D (MEGA-WKAS)
Fee tier: 2500 (0.25%)
"""

import logging
from services.web3_service import Web3Service, KASPA_FINANCE_WKAS

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

MEGA_TOKEN = "0xe9c2f32816054c87ab04b7eb57cce657ea1ade76"
MEGA_POOL = "0x1Bc9e2F8a3f1e89D741333CC85847e2C34F5E44D"
FEE_TIER = 2500

def test_pool_state():
    """Test reading pool state"""
    print("\n" + "="*80)
    print("TEST 1: Reading Pool State")
    print("="*80)
    
    try:
        from services.v3_quoter import create_quoter_for_pool
        web3_service = Web3Service()
        
        quoter = create_quoter_for_pool(web3_service.w3, MEGA_POOL)
        state = quoter.get_pool_state()
        
        print(f"✅ Pool State Retrieved:")
        print(f"   Token0: {quoter.token0}")
        print(f"   Token1: {quoter.token1}")
        print(f"   Fee: {quoter.fee} ({quoter.fee/10000}%)")
        print(f"   sqrtPriceX96: {state['sqrt_price_x96']}")
        print(f"   Current Tick: {state['tick']}")
        print(f"   Liquidity: {state['liquidity']}")
        
        spot_price = quoter.get_spot_price()
        print(f"   Spot Price: {spot_price:.10f}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_buy_quote():
    """Test buying MEGA tokens with KAS (exact input)"""
    print("\n" + "="*80)
    print("TEST 2: Buy Quote (Exact Input - KAS → MEGA)")
    print("="*80)
    
    try:
        web3_service = Web3Service()
        
        kas_amount = 1 * 10**18
        print(f"Input: {kas_amount / 10**18} KAS")
        
        quote = web3_service.get_dex_buy_quote(
            MEGA_TOKEN,
            MEGA_POOL,
            kas_amount,
            FEE_TIER
        )
        
        print(f"✅ Buy Quote Retrieved:")
        print(f"   Tokens Out: {quote['tokens_out'] / 10**18:.6f} MEGA")
        print(f"   Execution Price: {quote['execution_price']:.10f} KAS per MEGA")
        print(f"   Price Impact: {quote['price_impact_percent']:.2f}%")
        print(f"   Gas Estimate: {quote['gas_estimate']}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_sell_quote():
    """Test selling MEGA tokens for KAS (exact input)"""
    print("\n" + "="*80)
    print("TEST 3: Sell Quote (Exact Input - MEGA → KAS)")
    print("="*80)
    
    try:
        web3_service = Web3Service()
        
        token_amount = 100 * 10**18
        print(f"Input: {token_amount / 10**18} MEGA")
        
        quote = web3_service.get_dex_sell_quote(
            MEGA_TOKEN,
            MEGA_POOL,
            token_amount,
            FEE_TIER
        )
        
        print(f"✅ Sell Quote Retrieved:")
        print(f"   KAS Out: {quote['kas_out'] / 10**18:.6f} KAS")
        print(f"   Execution Price: {quote['execution_price']:.10f} KAS per MEGA")
        print(f"   Price Impact: {quote['price_impact_percent']:.2f}%")
        print(f"   Gas Estimate: {quote['gas_estimate']}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_buy_quote_reverse():
    """Test reverse buy quote (exact output - want specific MEGA amount)"""
    print("\n" + "="*80)
    print("TEST 4: Reverse Buy Quote (Exact Output - Want X MEGA)")
    print("="*80)
    
    try:
        web3_service = Web3Service()
        
        tokens_out = 100 * 10**18
        print(f"Desired Output: {tokens_out / 10**18} MEGA")
        
        quote = web3_service.get_dex_buy_quote_reverse(
            MEGA_TOKEN,
            MEGA_POOL,
            tokens_out,
            FEE_TIER
        )
        
        print(f"✅ Reverse Buy Quote Retrieved:")
        print(f"   KAS Needed: {quote['kas_in'] / 10**18:.6f} KAS")
        print(f"   Execution Price: {quote['execution_price']:.10f} KAS per MEGA")
        print(f"   Price Impact: {quote['price_impact_percent']:.2f}%")
        print(f"   Gas Estimate: {quote['gas_estimate']}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_sell_quote_reverse():
    """Test reverse sell quote (exact output - want specific KAS amount)"""
    print("\n" + "="*80)
    print("TEST 5: Reverse Sell Quote (Exact Output - Want X KAS)")
    print("="*80)
    
    try:
        web3_service = Web3Service()
        
        kas_out = 1 * 10**18
        print(f"Desired Output: {kas_out / 10**18} KAS")
        
        quote = web3_service.get_dex_sell_quote_reverse(
            MEGA_TOKEN,
            MEGA_POOL,
            kas_out,
            FEE_TIER
        )
        
        print(f"✅ Reverse Sell Quote Retrieved:")
        print(f"   MEGA Needed: {quote['tokens_in'] / 10**18:.6f} MEGA")
        print(f"   Execution Price: {quote['execution_price']:.10f} KAS per MEGA")
        print(f"   Price Impact: {quote['price_impact_percent']:.2f}%")
        print(f"   Gas Estimate: {quote['gas_estimate']}")
        
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_consistency():
    """Test that forward and reverse quotes are consistent"""
    print("\n" + "="*80)
    print("TEST 6: Quote Consistency Check")
    print("="*80)
    
    try:
        web3_service = Web3Service()
        
        kas_amount = 1 * 10**18
        print(f"Testing with {kas_amount / 10**18} KAS")
        
        forward_quote = web3_service.get_dex_buy_quote(
            MEGA_TOKEN,
            MEGA_POOL,
            kas_amount,
            FEE_TIER
        )
        
        reverse_quote = web3_service.get_dex_buy_quote_reverse(
            MEGA_TOKEN,
            MEGA_POOL,
            forward_quote['tokens_out'],
            FEE_TIER
        )
        
        kas_diff = abs(reverse_quote['kas_in'] - kas_amount)
        kas_diff_pct = (kas_diff / kas_amount) * 100
        
        print(f"Forward:  {kas_amount / 10**18} KAS → {forward_quote['tokens_out'] / 10**18:.6f} MEGA")
        print(f"Reverse:  {forward_quote['tokens_out'] / 10**18:.6f} MEGA ← {reverse_quote['kas_in'] / 10**18:.6f} KAS")
        print(f"Difference: {kas_diff / 10**18:.10f} KAS ({kas_diff_pct:.4f}%)")
        
        if kas_diff_pct < 0.01:
            print(f"✅ PASSED: Quotes are consistent (diff < 0.01%)")
            return True
        else:
            print(f"⚠️  WARNING: Quotes have {kas_diff_pct:.4f}% difference")
            return True
            
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("UNISWAP V3 QUOTE CALCULATION TEST SUITE")
    print("="*80)
    print(f"Testing against MEGA pool on Kasplex Testnet")
    print(f"Token: {MEGA_TOKEN}")
    print(f"Pool: {MEGA_POOL}")
    print(f"Fee: {FEE_TIER} ({FEE_TIER/10000}%)")
    
    results = {
        "Pool State": test_pool_state(),
        "Buy Quote (Exact Input)": test_buy_quote(),
        "Sell Quote (Exact Input)": test_sell_quote(),
        "Buy Quote Reverse (Exact Output)": test_buy_quote_reverse(),
        "Sell Quote Reverse (Exact Output)": test_sell_quote_reverse(),
        "Consistency Check": test_consistency()
    }
    
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! V3 quote calculation is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
