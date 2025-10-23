# GraduationController V2 End-to-End Test Report
## Token: RAGR (RoadRagers)

**Test Date**: October 23, 2025  
**Tester**: Replit Agent  
**Environment**: Kasplex Testnet (Chain ID: 167012)  

---

## Phase 1: Token Selection

### Selected Token: RAGR (RoadRagers)
- **Contract Address**: `0xa75c9441ba642165df45fbcdb03b5627521ecb7a`
- **Token ID**: 63
- **Created**: October 22, 2025

**Selection Rationale**:
- Market cap: $63.26 (exceeds $50 threshold ✅)
- Already in `graduating=True` state on-chain
- Has 12.3 KAS in treasury (sufficient for liquidity)
- Low value test token (safe for testing)

---

## Phase 2: Pre-Graduation Baseline State

### Database State (Before Completion)
```
ID: 63
Symbol: RAGR
Name: RoadRagers
Contract Address: 0xa75c9441ba642165df45fbcdb03b5627521ecb7a
Graduation Status: active
Market Cap: $62.03
KAS Reserve: 1217.701 KAS
Token Reserve: Not captured in DB
Created: 2025-10-22 06:46:08
Initiated At: NULL
Completion TX: NULL
DEX Pool Address: NULL
```

### On-Chain State (Bonding Pool)
```
Graduating: TRUE ✅
Virtual KAS Reserve: 1,217.701 KAS
Treasury KAS Balance: 12.3 KAS ✅
Token Reserve: 250,000,000 tokens (250M)
```

### GraduationController State
```
New GraduationController V2: 0x147e3ecbe189bb301175001706ff1f44df33b3ab
  Balance: 0 KAS

Old GraduationController V1: 0x9416D5a5D61ec70C18D1FE1039f8026E29b4820e
  Balance: 6,858.33 KAS (from previous tokens)
```

### Expected Liquidity Parameters
Based on bonding curve graduation logic:
- **Expected KAS for Liquidity**: ~12.3 KAS (treasury balance)
- **Expected Token Amount**: 25% of total supply = 250M tokens
- **Pool Fee Tier**: 0.25% (2500 basis points)
- **Tick Range**: Full range (-887220 to 887220)

### Expected sqrtPriceX96 Calculation
```
price = kasAmount / tokenAmount
price = 12.3 / 250,000,000
price = 0.0000000492 KAS per token

sqrtPriceX96 = sqrt(price) * 2^96
sqrtPriceX96 = sqrt(0.0000000492) * 79228162514264337593543950336
sqrtPriceX96 = 0.000221809 * 79228162514264337593543950336
sqrtPriceX96 ≈ 17,570,824,045,140,000 (estimated)
```

---

## Phase 3: Graduation Trigger (IN PROGRESS)

**Method**: Automated graduation_completion_service
**Oracle Wallet**: 0x5f837F62744D4d80Fc79C3A5346B4A228956914E
**Oracle Balance**: 2,012.99 KAS

### Transaction Details
- **Initiation TX**: Not found in database (likely initiated manually or lost)
- **Completion TX**: Pending...

---

## Critical Issues Found

### Issue 1: KTR Token Graduation Failure
**Token**: KTR (Kaspertron)  
**Error**: `InsufficientKAS()` (0x8bbc6532)

**Root Cause**: Configuration mismatch between OLD and NEW GraduationController
- KTR was initiated with OLD controller (0x9416...)
- System trying to complete with NEW controller (0x147e...)
- KAS stuck in OLD controller (6,858.33 KAS)
- NEW controller has 0 KAS

**Recommendation**: 
- Reset KTR's graduation state
- Re-initiate with correct controller
- OR migrate KAS from old to new controller

### Issue 2: RAGR Database State Mismatch
**Token**: RAGR (RoadRagers)  
**Discrepancy**: On-chain `graduating=True` but DB shows `graduation_status='active'`

**Impact**: Database not updated when graduation was initiated  
**Recommendation**: Update database state tracking in graduation monitor

---

## Next Steps
1. Complete RAGR graduation
2. Monitor transaction and capture events
3. Verify post-graduation state
4. Document results

**Status**: ⏳ IN PROGRESS
