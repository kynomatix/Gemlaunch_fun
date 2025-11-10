# Kasplex WebSocket Test Results
**Date:** November 6, 2025  
**Project:** Gemlaunch.fun  
**Tester:** Gemlaunch Engineering Team

---

## Request

We're building a real-time trading platform on Kasplex zkEVM Testnet and need WebSocket support for `eth_subscribe` to eliminate polling latency. Mirza mentioned Kaspa Finance uses `wss://ws.kasplextest.xyz` successfully.

---

## Test Results

### ❌ Test 1: wss://ws.kasplextest.xyz
**Status:** Connection Refused  
**Error:** `[Errno 111] Connect call failed ('54.154.73.46', 443)`  
**Interpretation:** No server listening on this endpoint

### ❌ Test 2: wss://rpc.kasplextest.xyz
**Status:** HTTP 400 Bad Request  
**Error:** `server rejected WebSocket connection: HTTP 400`  
**Interpretation:** Server exists but rejects WebSocket handshake

### ✅ Test 3: https://rpc.kasplextest.xyz (HTTP)
**Status:** Working Perfect  
**Current Block:** 10,076,802  
**Latency:** 313ms  
**Interpretation:** HTTP RPC is fully operational

---

## What We Tried

1. **Multiple paths tested:**
   - `wss://rpc.kasplextest.xyz`
   - `wss://rpc.kasplextest.xyz/ws`
   - `wss://rpc.kasplextest.xyz/websocket`
   - `wss://ws.kasplextest.xyz`
   - (and several variations)

2. **Multiple configurations:**
   - Standard WebSocket handshake
   - Different Origin headers
   - Various timeout settings

---

## Questions for Kasplex Team

1. **Is WebSocket RPC enabled** on Kasplex zkEVM Testnet?
   - If yes, what is the correct endpoint?
   - If no, when will it be available?

2. **Does the endpoint require:**
   - Authentication/API keys?
   - Specific headers or subprotocols?
   - Allowlist of origins?

3. **Does eth_subscribe work** for:
   - `newHeads` (block headers)?
   - `logs` (contract events)?
   - `pendingTransactions`?

4. **Is WebSocket testnet-only or mainnet-only?**

5. **How does Kaspa Finance connect?**
   - Can you share example connection code?
   - Or point us to their implementation?

---

## Our Use Case

**Platform:** Gemlaunch.fun (Memecoin Launchpad)  
**Network:** Kasplex zkEVM Testnet (Chain ID: 167012)  
**Current Issue:** 30-second polling → 42s average latency  
**Goal:** Real-time trade updates via WebSocket subscriptions  
**Expected Improvement:** <3s latency (94% faster)

**What we need WebSocket for:**
- Subscribe to new blocks (`newHeads`)
- Subscribe to token trade events (`logs`)
- Broadcast real-time updates to users

---

## Fallback Plan

If WebSocket is unavailable, we can proceed with:
- **2-second HTTP fast polling** (still 90% faster than current)
- **Flask-SocketIO** to push updates to users
- **Expected latency:** ~2.5s (vs current 42s)

But native WebSocket would be optimal for:
- Lower server load
- Better latency (<2s)
- More efficient resource usage

---

## Contact

Please respond with:
1. Correct WebSocket endpoint (if available)
2. Any authentication requirements
3. Timeline if not yet enabled
4. Example connection code if possible

Thank you!

---

**Test Script Available:**
- Full test suite: `scripts/test_kasplex_websocket.py`
- Can run additional tests as needed
- Happy to help debug connection issues
