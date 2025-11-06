#!/usr/bin/env python3
"""
Kasplex WebSocket Path Discovery Script
Tests different WebSocket paths and configurations
"""

import asyncio
import json
import websockets
from websockets.client import WebSocketClientProtocol
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_websocket_path(base_url, path="", extra_headers=None):
    """Test a specific WebSocket path"""
    full_url = f"{base_url}{path}"
    headers = extra_headers or {}
    
    try:
        logger.info(f"Testing: {full_url}")
        if headers:
            logger.info(f"  Headers: {headers}")
        
        async with websockets.connect(
            full_url,
            extra_headers=headers,
            ping_interval=None,
            close_timeout=5
        ) as ws:
            logger.info(f"✅ CONNECTED to {full_url}")
            
            # Try eth_blockNumber
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
                logger.info(f"✅ RPC WORKS! Current block: {block}")
                
                # Try eth_subscribe
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }
                
                await ws.send(json.dumps(subscribe_request))
                sub_response = await asyncio.wait_for(ws.recv(), timeout=5)
                sub_data = json.loads(sub_response)
                
                if 'result' in sub_data:
                    logger.info(f"✅ eth_subscribe WORKS! Subscription: {sub_data['result']}")
                    return 'full_support'
                elif 'error' in sub_data:
                    logger.warning(f"⚠️  eth_subscribe not supported: {sub_data['error']['message']}")
                    return 'rpc_only'
            else:
                logger.warning(f"⚠️  Unexpected response: {data}")
                return 'connected'
            
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ HTTP {e.status_code}: {e.headers.get('Server', 'Unknown')}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout")
        return None
    except Exception as e:
        logger.error(f"❌ Error: {type(e).__name__}: {e}")
        return None


async def main():
    """Test various WebSocket configurations"""
    
    base_urls = [
        "wss://rpc.kasplextest.xyz",
        "wss://ws.kasplextest.xyz"
    ]
    
    paths = [
        "",           # No path
        "/",          # Root
        "/ws",        # Common WebSocket path
        "/websocket", # Another common path
        "/rpc",       # RPC path
        "/v1",        # Versioned path
    ]
    
    headers_variations = [
        {},  # No extra headers
        {"Origin": "https://gemlaunch.fun"},  # Set origin
        {"User-Agent": "Mozilla/5.0"},  # Browser-like
    ]
    
    logger.info("=" * 70)
    logger.info("KASPLEX WEBSOCKET PATH DISCOVERY")
    logger.info("=" * 70)
    
    results = []
    
    for base_url in base_urls:
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing base URL: {base_url}")
        logger.info(f"{'='*70}\n")
        
        for path in paths:
            for headers in headers_variations:
                result = await test_websocket_path(base_url, path, headers)
                if result:
                    results.append({
                        'url': f"{base_url}{path}",
                        'headers': headers,
                        'support': result
                    })
                    logger.info(f"🎯 FOUND WORKING CONFIG!")
                    logger.info(f"   URL: {base_url}{path}")
                    logger.info(f"   Headers: {headers}")
                    logger.info(f"   Support: {result}")
                    break  # Found working config
            
            if result:
                break  # Found working config
        
        if result:
            break  # Found working config
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    
    if results:
        logger.info(f"\n✅ Found {len(results)} working configuration(s):\n")
        for i, r in enumerate(results, 1):
            logger.info(f"{i}. {r['url']}")
            logger.info(f"   Headers: {r['headers']}")
            logger.info(f"   Support: {r['support']}")
            logger.info("")
    else:
        logger.error("\n❌ No working WebSocket configuration found")
        logger.info("\nRecommendation: Contact Kasplex team or check documentation")
        logger.info("- Verify WebSocket endpoint in official docs")
        logger.info("- Ask if authentication/API keys required")
        logger.info("- Check if WebSocket is testnet-only or mainnet-only")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Discovery interrupted")
    except Exception as e:
        logger.error(f"\n\n❌ Discovery failed: {e}")
        raise
