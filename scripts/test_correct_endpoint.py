#!/usr/bin/env python3
"""
Test the EXACT endpoint provided: ws.kasplextest.xyz
Try different protocols and ports
"""

import asyncio
import json
import websockets

async def test(url):
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    
    try:
        ws = await websockets.connect(url, ping_interval=None)
        print("✅ CONNECTED!")
        
        # eth_blockNumber
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_blockNumber",
            "params": []
        }))
        
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(response)
        
        if 'result' in data:
            block = int(data['result'], 16)
            print(f"✅ Block: {block}")
            
            # eth_subscribe
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_subscribe",
                "params": ["newHeads"]
            }))
            
            sub_resp = await asyncio.wait_for(ws.recv(), timeout=5)
            sub_data = json.loads(sub_resp)
            
            if 'result' in sub_data:
                print(f"✅ eth_subscribe WORKS! ID: {sub_data['result']}")
                print(f"\n🎉 SUCCESS! Endpoint: {url}")
                await ws.close()
                return True
            else:
                print(f"Response: {sub_data}")
        
        await ws.close()
        
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
    
    return False

async def main():
    # Test variations of ws.kasplextest.xyz
    endpoints = [
        "wss://ws.kasplextest.xyz",       # Secure WebSocket
        "ws://ws.kasplextest.xyz",        # Non-secure
        "wss://ws.kasplextest.xyz:443",   # Explicit HTTPS port
        "wss://ws.kasplextest.xyz:8545",  # Common Ethereum port
        "ws://ws.kasplextest.xyz:80",     # HTTP port
        "ws://ws.kasplextest.xyz:8546",   # Common WS port
    ]
    
    print("Testing ws.kasplextest.xyz with different protocols/ports...")
    
    for endpoint in endpoints:
        if await test(endpoint):
            break

asyncio.run(main())
