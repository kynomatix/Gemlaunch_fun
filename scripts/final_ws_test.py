#!/usr/bin/env python3
"""
Direct WebSocket test - no fancy libraries
Just raw WebSocket + JSON-RPC like a normal person would do it
"""

import asyncio
import json
import websockets

async def test(url):
    print(f"\nTesting: {url}")
    print("="*60)
    
    try:
        ws = await websockets.connect(url)
        print("✅ Connected!")
        
        # Send eth_blockNumber request
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_blockNumber",
            "params": []
        }))
        
        response = await ws.recv()
        data = json.loads(response)
        
        if 'result' in data:
            block = int(data['result'], 16)
            print(f"✅ Block number: {block}")
            print(f"✅ WebSocket RPC WORKS!")
            
            # Try subscribe
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_subscribe",
                "params": ["newHeads"]
            }))
            
            sub_response = await ws.recv()
            sub_data = json.loads(sub_response)
            
            if 'result' in sub_data:
                print(f"✅ eth_subscribe WORKS! ID: {sub_data['result']}")
                print("\n🎉 FULL SUCCESS - Ready for production!")
                await ws.close()
                return True
            else:
                print(f"❌ eth_subscribe failed: {sub_data}")
        
        await ws.close()
        
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return False

async def main():
    urls = [
        "wss://rpc.kasplextest.xyz",
        "ws://rpc.kasplextest.xyz",  # Try non-TLS
    ]
    
    for url in urls:
        if await test(url):
            break

asyncio.run(main())
