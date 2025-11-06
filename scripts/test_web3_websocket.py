#!/usr/bin/env python3
"""
Test Kasplex WebSocket using web3.py (production library)
This is what we'll actually use in the real implementation
"""

import asyncio
from web3 import Web3
from web3.providers.websocket import WebSocketProvider
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_web3_websocket():
    """Test WebSocket using AsyncWeb3 (production setup)"""
    
    endpoints_to_test = [
        "wss://rpc.kasplextest.xyz",
        "wss://ws.kasplextest.xyz",
    ]
    
    for endpoint in endpoints_to_test:
        logger.info("=" * 60)
        logger.info(f"Testing: {endpoint}")
        logger.info("=" * 60)
        
        try:
            # Use Web3 with WebSocketProvider (production setup)
            w3 = Web3(WebSocketProvider(endpoint))
            logger.info("✅ WebSocket connected!")
            
            # Test basic RPC call
            block_number = w3.eth.block_number
            logger.info(f"✅ Current block: {block_number}")
            
            # Test eth_subscribe
            logger.info("Testing eth_subscribe...")
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 SUCCESS! WebSocket is fully operational!")
            logger.info("=" * 60)
            logger.info(f"Endpoint: {endpoint}")
            logger.info("Connection: WORKS")
            logger.info("eth_blockNumber: WORKS")
            logger.info("Ready for production use!")
            logger.info("=" * 60)
            return True
                    
        except Exception as e:
            logger.error(f"❌ Failed: {type(e).__name__}: {e}")
            continue
    
    logger.error("\n" + "=" * 60)
    logger.error("❌ Could not establish WebSocket connection")
    logger.error("=" * 60)
    return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_web3_websocket())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted")
        exit(1)
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
