#!/usr/bin/env python3
"""
Simple Kasplex WebSocket Test
Direct test using websockets library
"""

import asyncio
import json
import websockets

async def test_endpoint(url):
    """Test a WebSocket endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    
    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            print(f"✅ CONNECTED!")
            
            # Test eth_blockNumber
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_blockNumber",
                "params": []
            }
            
            await ws.send(json.dumps(request))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            
            if 'result' in data:
                block = int(data['result'], 16)
                print(f"✅ eth_blockNumber works! Block: {block}")
                
                # Test eth_subscribe
                subscribe_req = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }
                
                await ws.send(json.dumps(subscribe_req))
                sub_response = await asyncio.wait_for(ws.recv(), timeout=5)
                sub_data = json.dumps(sub_response)
                
                if 'result' in sub_data:
                    print(f"✅ eth_subscribe SUPPORTED! 🎉")
                    print(f"   Subscription ID: {sub_data['result']}")
                    return True
                else:
                    print(f"❌ eth_subscribe NOT supported")
                    print(f"   Response: {sub_data}")
                    return False
            else:
                print(f"❌ Unexpected response: {data}")
                return False
                
    except Exception as e:
        print(f"❌ Failed: {type(e).__name__}: {str(e)}")
        return False


async def main():
    urls_to_test = [
        "wss://rpc.kasplextest.xyz",
        "wss://rpc.kasplextest.xyz/",
        "wss://rpc.kasplextest.xyz/ws",
        "wss://ws.kasplextest.xyz",
        "wss://ws.kasplextest.xyz/",
    ]
    
    print("\n🚀 Kasplex WebSocket Discovery")
    print("="*60)
    
    for url in urls_to_test:
        result = await test_endpoint(url)
        if result:
            print(f"\n🎯 SUCCESS! Use this endpoint: {url}")
            break
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(main())
