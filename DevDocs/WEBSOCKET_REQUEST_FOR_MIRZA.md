# WebSocket Endpoint Request for Kasplex zkEVM Testnet

**To:** Mirza / Kasplex Team  
**From:** Gemlaunch.fun Engineering  
**Date:** November 6, 2025

---

## Issue

We're building a real-time trading platform on Kasplex zkEVM Testnet and **NEED WebSocket** for `eth_subscribe` to avoid polling. Polling creates unacceptable performance issues:
- Dashboard slowdowns
- Page load delays
- System bloat
- Poor trading UX

You mentioned Kaspa Finance uses WebSocket successfully. We need the exact configuration.

---

## What We've Tried

### Endpoint 1: `ws.kasplextest.xyz` (as you mentioned)
**Result:** `Connection Refused` on ALL ports (443, 80, 8545, 8546)  
**Details:** No server listening at IP 54.154.73.46

### Endpoint 2: `wss://rpc.kasplextest.xyz`
**Result:** `HTTP 400 - server rejected WebSocket connection`  
**Details:** Server expects HTTP JSON-RPC, not WebSocket upgrade

**HTTP RPC works perfectly:** `https://rpc.kasplextest.xyz` ✅

**Test code:**
```python
import websockets
import json

# Tried both:
# wss://ws.kasplextest.xyz - Connection refused
# wss://rpc.kasplextest.xyz - HTTP 400
```

---

## What We Need

**1. Correct WebSocket endpoint:**
- Is it `wss://rpc.kasplextest.xyz`?
- Or something else (like `wss://ws.kasplextest.xyz`)?

**2. Connection requirements:**
- Any specific headers needed?
- Any subprotocol requirements?
- Different path (like `/ws` or `/websocket`)?

**3. Supported methods:**
- Does `eth_subscribe` work for `newHeads`?
- Does `eth_subscribe` work for `logs`?

**4. How does Kaspa Finance connect?**
- Can you share example connection code?
- Or test their live endpoint yourself?

---

## Our Use Case

- **Platform:** Gemlaunch.fun (Memecoin Launchpad)
- **Network:** Kasplex zkEVM Testnet (Chain ID: 167012)
- **Need:** Real-time trade event subscriptions
- **Why WebSocket:** Polling creates dashboard slowdowns and poor trading experience

---

## Urgency

WebSocket is **blocking** our migration plan. We have full implementation ready but can't proceed without the correct endpoint.

Please provide:
1. Exact WebSocket URL
2. Connection example (if non-standard)
3. Or confirmation if WebSocket isn't enabled on testnet yet

---

**Thank you!**

Test script available if you want to verify:
`scripts/test_kasplex_websocket.py`
