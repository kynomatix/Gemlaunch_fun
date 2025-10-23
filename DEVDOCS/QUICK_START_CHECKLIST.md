# GraduationController V2 - Quick Start Checklist

**🚨 IMMEDIATE ACTION REQUIRED 🚨**

Your current graduation system is **100% broken**. Follow this checklist to deploy the fixed V2 contract.

---

## ⚡ CRITICAL ISSUES IN V1 (Currently Deployed)

| Issue | Impact | Status |
|-------|--------|--------|
| Missing pool creation | All graduations fail | ❌ CRITICAL |
| Missing price initialization | All graduations fail | ❌ CRITICAL |
| Broken token transfer | All graduations fail | ❌ CRITICAL |
| No validation | Security risk | ⚠️ HIGH |
| No emergency functions | Funds stuck forever | ⚠️ HIGH |

**Result**: 6858 KAS stuck, 100% failure rate, frustrated users

---

## ✅ 5-MINUTE QUICK START

### Step 1: Review the Audit (5 min)
- [ ] Read `EXECUTIVE_SUMMARY.md` (this is the big picture)
- [ ] Skim `GRADUATION_CONTRACT_SECURITY_AUDIT.md` (focus on Critical Issues section)

### Step 2: Prepare Environment (10 min)
```bash
# Install dependencies
npm install @openzeppelin/contracts@^5.0.0

# Set environment variables
export KASPA_TESTNET_RPC="your_rpc_url"
export DEPLOYER_PRIVATE_KEY="your_private_key"
export UNISWAP_V3_FACTORY="0x1b72D7165a0D7256a4F197765C15bb70bC5D66A8"
export UNISWAP_V3_POSITION_MANAGER="0x4E25637cF39822364b877F81B18c5B6CF0eeF589"
export WKAS_ADDRESS="0xD18FCd278F7156DaA2a506dBC2A4a15337B91b94"
export TOKEN_FACTORY="your_token_factory_address"
export GRADUATION_ORACLE="your_oracle_address"
```

### Step 3: Deploy V2 to Testnet (5 min)
```bash
# Compile
npx hardhat compile

# Deploy
npx hardhat run scripts/deployGraduationV2.js --network kaspaTestnet

# Verify
npx hardhat verify --network kaspaTestnet <DEPLOYED_ADDRESS> <CONSTRUCTOR_ARGS>
```

### Step 4: Test (30 min)
- [ ] Create test token
- [ ] Buy to $50 market cap
- [ ] Call `initiateGraduation()`
- [ ] Call `completeGraduation()`
- [ ] Verify pool exists on Uniswap
- [ ] Verify can trade

### Step 5: Update Backend (15 min)
```typescript
// Update contract address
const GRADUATION_CONTROLLER_ADDRESS = "new_v2_address";

// Update ABI (use V2 ABI with new functions)
```

### Step 6: Deploy to Production (1 hour)
- [ ] Test 10 graduations on testnet
- [ ] Deploy V2 to mainnet
- [ ] Update production backend
- [ ] Monitor first graduation

---

## 📋 TESTNET TESTING CHECKLIST

Before deploying to production, verify:

### Basic Functionality
- [ ] Contract deploys successfully
- [ ] All addresses set correctly
- [ ] Can call `initiateGraduation()` as oracle
- [ ] Can call `completeGraduation()` as oracle
- [ ] Non-oracle cannot call graduation functions
- [ ] Owner can call admin functions

### Uniswap Integration
- [ ] Pool is created (check factory.getPool())
- [ ] Pool is initialized (check slot0.sqrtPriceX96 != 0)
- [ ] Liquidity is minted (check positionId > 0)
- [ ] Can swap on Uniswap V3 after graduation

### State Management
- [ ] `hasGraduated[token]` becomes true
- [ ] `graduationTimestamp[token]` is set
- [ ] `liquidityPositionId[token]` is set
- [ ] `uniswapPoolAddress[token]` is set
- [ ] Pool state: `graduated = true`

### Edge Cases
- [ ] Graduation with minimum liquidity
- [ ] Graduation with maximum liquidity
- [ ] Token with address < WKAS
- [ ] Token with address > WKAS
- [ ] Multiple graduations in sequence

### Error Handling
- [ ] Cannot graduate twice
- [ ] Cannot complete before initiate
- [ ] Proper revert messages
- [ ] Events emitted correctly

### Emergency Functions
- [ ] Can pause contract
- [ ] Can unpause contract
- [ ] Can cancel graduation
- [ ] Can emergency withdraw
- [ ] Cannot withdraw graduated tokens

---

## 🔥 COMMON MISTAKES TO AVOID

### ❌ DON'T
- Deploy V2 to mainnet before testing on testnet
- Skip the manual graduation test
- Update backend before V2 is tested
- Deploy without verifying on explorer
- Ignore gas usage testing
- Skip emergency function testing

### ✅ DO
- Test on testnet first (at least 10 graduations)
- Verify contract on explorer immediately
- Monitor first production graduations closely
- Have emergency procedures ready
- Document everything
- Staged rollout (1 token, 5 tokens, then all)

---

## 🎯 SUCCESS METRICS

Track these after deployment:

| Metric | V1 | V2 Target |
|--------|-----|-----------|
| Graduation Success Rate | 0% | 100% |
| Gas Cost | N/A (fails) | < 1M |
| Stuck Funds | 6858 KAS | 0 KAS |
| Average Time | N/A | < 5 min |
| User Satisfaction | 😡 | 😊 |

---

## 📞 EMERGENCY PROCEDURES

### If Graduation Fails on Testnet
1. Check transaction logs for revert reason
2. Verify pool was created: `factory.getPool(token, WKAS, 2500)`
3. Verify pool was initialized: `pool.slot0().sqrtPriceX96`
4. Check if funds are stuck: `controller.balance`
5. If stuck, call `cancelGraduation(tokenAddress)`

### If Graduation Fails on Mainnet
1. **IMMEDIATELY** pause contract: `controller.pause()`
2. Alert team in emergency channel
3. Investigate logs and events
4. If critical bug: deploy V2.1 with fix
5. If recoverable: use `cancelGraduation()`
6. Document incident and create post-mortem

### Emergency Contact Commands
```bash
# Pause graduations
cast send <CONTROLLER> "pause()" --private-key <OWNER_KEY>

# Cancel stuck graduation
cast send <CONTROLLER> "cancelGraduation(address)" <TOKEN> --private-key <OWNER_KEY>

# Emergency withdraw
cast send <CONTROLLER> "emergencyWithdraw(address,uint256)" <TOKEN> <AMOUNT> --private-key <OWNER_KEY>

# Check if paused
cast call <CONTROLLER> "paused()(bool)"
```

---

## 📚 FILE REFERENCE

| File | Purpose | Read Time |
|------|---------|-----------|
| EXECUTIVE_SUMMARY.md | Overview & roadmap | 15 min |
| GRADUATION_CONTRACT_SECURITY_AUDIT.md | Detailed audit | 45 min |
| GraduationControllerV2.sol | New contract code | 30 min |
| DEPLOYMENT_AND_TESTING_GUIDE.md | How to deploy | 60 min |

**Recommended Reading Order**:
1. This file (5 min) - Get oriented
2. EXECUTIVE_SUMMARY.md (15 min) - Understand scope
3. Audit Critical Issues section (10 min) - Know what was broken
4. GraduationControllerV2.sol (30 min) - Review the code
5. DEPLOYMENT_AND_TESTING_GUIDE.md (60 min) - Deploy safely

---

## 🚀 DEPLOYMENT TIMELINE

### Conservative Approach (Recommended)
- **Day 1**: Deploy to testnet, test 5 graduations
- **Day 2**: Test 10 more graduations, various scenarios
- **Day 3**: Fix any issues, test edge cases
- **Day 4**: Deploy to mainnet, update backend
- **Day 5**: Monitor first production graduation closely
- **Week 2**: Scale up to all tokens

### Aggressive Approach (Risky)
- **Day 1**: Deploy to testnet, test 3 graduations
- **Day 2**: Deploy to mainnet if tests pass
- **Day 3**: Monitor closely

**Recommendation**: Conservative approach. Better to be safe than sorry.

---

## ⚠️ RISK SUMMARY

### What Could Go Wrong
1. **Gas costs too high** → Test thoroughly, optimize if needed
2. **Price calculation wrong** → Validate against bonding curve
3. **Slippage too tight** → Adjust parameters via `setGraduationParams()`
4. **Backend timing issues** → Add retry logic
5. **Uniswap pool manipulation** → Price deviation check will catch it

### Mitigation Strategy
- Extensive testnet testing (10+ graduations)
- Close monitoring of first mainnet graduations
- Emergency pause function ready
- Staged rollout (not all tokens at once)
- Clear communication with users

---

## ✅ FINAL CHECKLIST BEFORE MAINNET

- [ ] 10+ successful graduations on testnet
- [ ] All test cases passed
- [ ] Gas usage < 1M per graduation
- [ ] No funds stuck in controller after tests
- [ ] Events emitted correctly
- [ ] Can trade on Uniswap after graduation
- [ ] Backend integration tested
- [ ] Emergency procedures documented
- [ ] Team trained on V2
- [ ] User communication prepared
- [ ] Monitoring/alerts configured
- [ ] Rollback plan documented

**Only deploy to mainnet when ALL boxes are checked.**

---

## 🎉 WHAT SUCCESS LOOKS LIKE

### Week 1 After Mainnet Deployment
- ✅ 5+ tokens graduated successfully
- ✅ 0 stuck funds
- ✅ All pools trading on Uniswap
- ✅ Gas costs within budget
- ✅ No emergency pauses needed
- ✅ Happy users

### Month 1 After Mainnet Deployment
- ✅ 50+ tokens graduated
- ✅ 100% success rate maintained
- ✅ Average gas cost optimized
- ✅ No critical issues found
- ✅ Positive user feedback
- ✅ V1 fully deprecated

---

## 💡 PRO TIPS

1. **Test with real tokens on testnet** - Don't use mocks for integration testing
2. **Monitor gas prices** - Deploy/graduate during low gas periods
3. **Use a separate oracle wallet** - Don't use the owner wallet as oracle
4. **Set up alerts** - Get notified of failed graduations immediately
5. **Document everything** - Every deployment, every configuration change
6. **Keep V1 address handy** - In case you need to reference it
7. **Save deployment transactions** - You'll need them for verification

---

## 📞 SUPPORT

If you get stuck:

1. **Check logs**: Most issues are visible in transaction logs
2. **Review audit**: The answer might be in the security audit
3. **Test in isolation**: Deploy fresh on testnet and test the specific scenario
4. **Ask for help**: Contact your team or external auditors

**Remember**: It's better to delay deployment than to rush and have issues.

---

## 🏁 QUICK WIN

**If you only have 1 hour today**:

1. Deploy V2 to testnet (15 min)
2. Create test token (10 min)
3. Graduate it successfully (30 min)
4. Celebrate! 🎉 (5 min)

That's all you need to prove V2 works. Everything else is about doing it safely at scale.

---

**Last Updated**: October 23, 2025  
**Status**: Ready for Testnet Deployment  
**Priority**: 🔥 CRITICAL 🔥

---

## START HERE ↓

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your values

# 2. Deploy to testnet
npm run deploy:testnet

# 3. Test graduation
npm run test:graduation

# 4. If successful, proceed to mainnet
npm run deploy:mainnet
```

**Good luck! You've got this.** 💪

---

*Questions? Check DEPLOYMENT_AND_TESTING_GUIDE.md for detailed instructions.*
