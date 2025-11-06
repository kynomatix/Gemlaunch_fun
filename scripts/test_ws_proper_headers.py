#!/usr/bin/env python3
"""
Test WebSocket with proper browser-like headers
HTTP 400 usually means missing/wrong headers in handshake
"""

import asyncio
import json
import websockets
from websockets.client import connect

async def test_with_headers(url, headers=None):
    """Test WebSocket with specific headers"""
    print(f"\nTesting: {url}")
    if headers:
        print(f"Headers: {headers}")
    print("="*70)
    
    try:
        # Create connection with custom headers
        extra_headers = headers or {}
        
        async with connect(
            url,
            extra_headers=extra_headers,
            subprotocols=[],  # No subprotocol
            ping_interval=None
        ) as ws:
            print("✅ CONNECTED!")
            
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
                print(f"✅ Block: {block}")
                
                # Test eth_subscribe
                sub_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }
                
                await ws.send(json.dumps(sub_request))
                sub_response = await asyncio.wait_for(ws.recv(), timeout=5)
                sub_data = json.loads(sub_response)
                
                if 'result' in sub_data:
                    print(f"✅ eth_subscribe WORKS! ID: {sub_data['result']}")
                    print("\n🎉 SUCCESS - WebSocket fully operational!")
                    return True
                elif 'error' in sub_data:
                    print(f"⚠️ eth_subscribe error: {sub_data['error']}")
                    return False
            else:
                print(f"Unexpected response: {data}")
                return False
                
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return False

async def main():
    """Try different header combinations"""
    
    url = "wss://rpc.kasplextest.xyz"
    
    # Try different header combinations
    header_variations = [
        # 1. No extra headers (what we've been doing)
        {},
        
        # 2. Standard browser headers
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://gemlaunch.fun"
        },
        
        # 3. With Accept header
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://gemlaunch.fun",
            "Accept": "*/*"
        },
        
        # 4. Try different origin (Kaspa Finance origin)
        {
            "Origin": "https://app.kaspafinance.io"
        },
        
        # 5. Try kasplex origin
        {
            "Origin": "https://frontend.kasplextest.xyz"
        },
        
        # 6. Null origin (some servers allow this)
        {
            "Origin": "null"
        },
    ]
    
    print("🔍 Testing WebSocket with different header combinations...")
    print("="*70)
    
    for i, headers in enumerate(header_variations, 1):
        print(f"\n{'='*70}")
        print(f"ATTEMPT {i}/{len(header_variations)}")
        print(f"{'='*70}")
        
        if await test_with_headers(url, headers):
            print(f"\n✅ Found working configuration!")
            print(f"Headers needed: {headers}")
            break
        
        await asyncio.sleep(0.5)  # Small delay between attempts
    
    else:
        print(f"\n❌ All header combinations failed")
        print(f"\nThis suggests:")
        print(f"1. WebSocket might not be enabled on this endpoint")
        print(f"2. Requires authentication we don't know about")
        print(f"3. Different endpoint altogether")

if __name__ == "__main__":
    asyncio.run(main())
