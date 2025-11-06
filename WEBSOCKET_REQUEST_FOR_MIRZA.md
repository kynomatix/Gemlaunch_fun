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

**Endpoint:** `wss://rpc.kasplextest.xyz`  
**Result:** `HTTP 400 - server rejected WebSocket connection`

The HTTP RPC works perfectly at `https://rpc.kasplextest.xyz`, but WebSocket handshake fails.

**Test code:**
```python
import websockets
import json

async with websockets.connect("wss://rpc.kasplextest.xyz") as ws:
    await ws.send(json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }))
    # ❌ Fails with HTTP 400
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
