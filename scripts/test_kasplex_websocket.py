#!/usr/bin/env python3
"""
Kasplex WebSocket Endpoint Test Script
Tests wss://ws.kasplextest.xyz for WebSocket + eth_subscribe support

This is Phase 0 of the WebSocket Migration Plan.
Results determine architecture: Native WebSocket vs Fast Polling.
"""

import asyncio
import json
import time
import websockets
from web3 import Web3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KasplexWebSocketTester:
    """Test Kasplex L2 WebSocket capabilities"""
    
    def __init__(self):
        # Correct WebSocket URL: Replace https:// with wss:// on same domain
        self.ws_endpoint = "wss://rpc.kasplextest.xyz"
        self.http_endpoint = "https://rpc.kasplextest.xyz"
        self.results = {}
        
    async def test_websocket_connection(self):
        """Test 1: Basic WebSocket connectivity"""
        logger.info("=" * 60)
        logger.info("TEST 1: WebSocket Connection")
        logger.info("=" * 60)
        
        try:
            start = time.time()
            async with websockets.connect(self.ws_endpoint, ping_interval=None) as ws:
                latency = (time.time() - start) * 1000
                logger.info(f"✅ WebSocket connection successful!")
                logger.info(f"   Endpoint: {self.ws_endpoint}")
                logger.info(f"   Connection latency: {latency:.2f}ms")
                
                self.results['websocket_available'] = True
                self.results['connection_latency_ms'] = latency
                return True
                
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.results['websocket_available'] = False
            self.results['connection_error'] = str(e)
            return False
    
    async def test_eth_subscribe_support(self):
        """Test 2: eth_subscribe support (for native push)"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: eth_subscribe Support")
        logger.info("=" * 60)
        
        try:
            async with websockets.connect(self.ws_endpoint, ping_interval=None) as ws:
                # Try subscribing to new block headers
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }
                
                await ws.send(json.dumps(subscribe_request))
                
                # Wait for response with timeout
                try:
                    response_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    response = json.loads(response_raw)
                    
                    if 'result' in response:
                        subscription_id = response['result']
                        logger.info(f"✅ eth_subscribe SUPPORTED!")
                        logger.info(f"   Subscription ID: {subscription_id}")
                        
                        # Try to receive one event
                        logger.info("   Waiting for first event (10s timeout)...")
                        try:
                            event_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            event = json.loads(event_raw)
                            logger.info(f"✅ Received event: {event.get('method', 'unknown')}")
                            logger.info(f"   Event data: {json.dumps(event, indent=2)[:200]}...")
                            
                            self.results['eth_subscribe_supported'] = True
                            self.results['native_push_events'] = True
                            return True
                            
                        except asyncio.TimeoutError:
                            logger.warning("⚠️  No events received in 10s (blockchain may be inactive)")
                            self.results['eth_subscribe_supported'] = True
                            self.results['native_push_events'] = False
                            return True
                        
                    elif 'error' in response:
                        logger.error(f"❌ eth_subscribe NOT supported")
                        logger.error(f"   Error: {response['error']}")
                        self.results['eth_subscribe_supported'] = False
                        self.results['error_message'] = response['error'].get('message', 'Unknown')
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("❌ No response to eth_subscribe (timeout)")
                    self.results['eth_subscribe_supported'] = False
                    return False
                    
        except Exception as e:
            logger.error(f"❌ eth_subscribe test failed: {e}")
            self.results['eth_subscribe_error'] = str(e)
            return False
    
    async def test_standard_rpc_methods(self):
        """Test 3: Standard JSON-RPC methods over WebSocket"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Standard RPC Methods over WebSocket")
        logger.info("=" * 60)
        
        try:
            async with websockets.connect(self.ws_endpoint, ping_interval=None) as ws:
                # Test eth_blockNumber
                block_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_blockNumber",
                    "params": []
                }
                
                start = time.time()
                await ws.send(json.dumps(block_request))
                response_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                latency = (time.time() - start) * 1000
                
                response = json.loads(response_raw)
                
                if 'result' in response:
                    block_num = int(response['result'], 16)
                    logger.info(f"✅ eth_blockNumber works over WebSocket!")
                    logger.info(f"   Current block: {block_num}")
                    logger.info(f"   RPC latency: {latency:.2f}ms")
                    
                    self.results['standard_rpc_supported'] = True
                    self.results['rpc_latency_ms'] = latency
                    self.results['current_block'] = block_num
                    return True
                else:
                    logger.error(f"❌ eth_blockNumber failed: {response}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Standard RPC test failed: {e}")
            return False
    
    async def test_http_fallback(self):
        """Test 4: HTTP RPC fallback (for comparison)"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: HTTP RPC Fallback")
        logger.info("=" * 60)
        
        try:
            w3 = Web3(Web3.HTTPProvider(self.http_endpoint))
            
            start = time.time()
            block_num = w3.eth.block_number
            latency = (time.time() - start) * 1000
            
            logger.info(f"✅ HTTP RPC works!")
            logger.info(f"   Endpoint: {self.http_endpoint}")
            logger.info(f"   Current block: {block_num}")
            logger.info(f"   HTTP latency: {latency:.2f}ms")
            
            self.results['http_rpc_available'] = True
            self.results['http_latency_ms'] = latency
            
            # Compare latencies
            if 'rpc_latency_ms' in self.results:
                ws_faster = self.results['rpc_latency_ms'] < latency
                diff = abs(self.results['rpc_latency_ms'] - latency)
                logger.info(f"\n   📊 Latency Comparison:")
                logger.info(f"      WebSocket: {self.results['rpc_latency_ms']:.2f}ms")
                logger.info(f"      HTTP:      {latency:.2f}ms")
                logger.info(f"      Winner:    {'WebSocket' if ws_faster else 'HTTP'} ({diff:.2f}ms faster)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ HTTP fallback test failed: {e}")
            self.results['http_rpc_available'] = False
            return False
    
    async def measure_block_time(self):
        """Test 5: Measure actual block time"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: Block Time Measurement")
        logger.info("=" * 60)
        logger.info("Waiting for 3 new blocks to measure block time...")
        
        try:
            w3 = Web3(Web3.HTTPProvider(self.http_endpoint))
            
            # Get current block
            start_block = w3.eth.block_number
            start_time = time.time()
            
            # Wait for 3 new blocks
            target_block = start_block + 3
            block_times = []
            last_block = start_block
            last_time = start_time
            
            timeout = 60  # 60 second timeout
            while time.time() - start_time < timeout:
                current_block = w3.eth.block_number
                
                if current_block > last_block:
                    current_time = time.time()
                    block_time = current_time - last_time
                    block_times.append(block_time)
                    
                    logger.info(f"   Block {current_block}: {block_time:.2f}s since last block")
                    
                    last_block = current_block
                    last_time = current_time
                    
                    if current_block >= target_block:
                        break
                
                await asyncio.sleep(0.5)
            
            if block_times:
                avg_block_time = sum(block_times) / len(block_times)
                logger.info(f"\n✅ Block time measured!")
                logger.info(f"   Samples: {len(block_times)}")
                logger.info(f"   Average: {avg_block_time:.2f}s")
                logger.info(f"   Min: {min(block_times):.2f}s")
                logger.info(f"   Max: {max(block_times):.2f}s")
                
                self.results['block_time_seconds'] = avg_block_time
                self.results['block_time_samples'] = len(block_times)
                return True
            else:
                logger.warning("⚠️  No new blocks observed in 60s")
                return False
                
        except Exception as e:
            logger.error(f"❌ Block time measurement failed: {e}")
            return False
    
    def print_summary(self):
        """Print comprehensive test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("FINAL SUMMARY & RECOMMENDATIONS")
        logger.info("=" * 60)
        
        # WebSocket Status
        ws_available = self.results.get('websocket_available', False)
        eth_sub_supported = self.results.get('eth_subscribe_supported', False)
        
        logger.info("\n🔌 WebSocket Connectivity:")
        logger.info(f"   Status: {'✅ AVAILABLE' if ws_available else '❌ UNAVAILABLE'}")
        if ws_available:
            logger.info(f"   Connection Latency: {self.results.get('connection_latency_ms', 0):.2f}ms")
        
        logger.info("\n📡 eth_subscribe Support:")
        logger.info(f"   Status: {'✅ SUPPORTED' if eth_sub_supported else '❌ NOT SUPPORTED'}")
        
        logger.info("\n⚡ Performance Metrics:")
        if 'rpc_latency_ms' in self.results:
            logger.info(f"   WebSocket RPC: {self.results['rpc_latency_ms']:.2f}ms")
        if 'http_latency_ms' in self.results:
            logger.info(f"   HTTP RPC: {self.results['http_latency_ms']:.2f}ms")
        if 'block_time_seconds' in self.results:
            logger.info(f"   Block Time: {self.results['block_time_seconds']:.2f}s")
        
        # Architecture Recommendation
        logger.info("\n" + "=" * 60)
        logger.info("🎯 ARCHITECTURE RECOMMENDATION")
        logger.info("=" * 60)
        
        if ws_available and eth_sub_supported:
            logger.info("✅ OPTION A: Native WebSocket with eth_subscribe")
            logger.info("   - Use AsyncWeb3 with WebsocketProvider")
            logger.info("   - Subscribe to newHeads and logs")
            logger.info("   - Lowest latency (~1-2s)")
            logger.info("   - Recommended for production")
            
        elif ws_available:
            logger.info("⚠️  OPTION B: WebSocket RPC (no subscriptions)")
            logger.info("   - WebSocket available but no eth_subscribe")
            logger.info("   - Use WebSocket for standard RPC calls")
            logger.info("   - Still need polling, but lower latency than HTTP")
            logger.info("   - Hybrid approach recommended")
            
        else:
            logger.info("⚠️  OPTION C: HTTP Fast Polling (Fallback)")
            logger.info("   - WebSocket unavailable")
            logger.info("   - Use 2-second HTTP polling with eventlet")
            logger.info("   - Higher latency but proven reliable")
            logger.info("   - Safe fallback option")
        
        # Expected Latency
        logger.info("\n📊 Expected End-to-End Latency:")
        
        block_time = self.results.get('block_time_seconds', 1.0)
        
        if ws_available and eth_sub_supported:
            # Native WebSocket: block_time + processing
            expected = block_time + 0.5
            logger.info(f"   Option A (Native WS): ~{expected:.1f}s")
            logger.info(f"      - Blockchain confirmation: {block_time:.1f}s")
            logger.info(f"      - WebSocket push: 0s")
            logger.info(f"      - Processing: 0.5s")
            
        elif ws_available:
            # WebSocket polling: block_time + poll_interval/2 + processing
            poll_interval = 2.0
            expected = block_time + (poll_interval / 2) + 0.5
            logger.info(f"   Option B (WS Polling): ~{expected:.1f}s")
            logger.info(f"      - Blockchain confirmation: {block_time:.1f}s")
            logger.info(f"      - Polling delay (avg): {poll_interval/2:.1f}s")
            logger.info(f"      - Processing: 0.5s")
        
        else:
            # HTTP polling: same as WebSocket polling
            poll_interval = 2.0
            expected = block_time + (poll_interval / 2) + 0.5
            logger.info(f"   Option C (HTTP Polling): ~{expected:.1f}s")
            logger.info(f"      - Blockchain confirmation: {block_time:.1f}s")
            logger.info(f"      - Polling delay (avg): {poll_interval/2:.1f}s")
            logger.info(f"      - Processing: 0.5s")
        
        logger.info("\n" + "=" * 60)
        logger.info("Next Steps:")
        logger.info("=" * 60)
        
        if ws_available and eth_sub_supported:
            logger.info("1. ✅ Proceed with Option A (Native WebSocket)")
            logger.info("2. Implement AsyncWeb3 WebsocketProvider in fast_indexer.py")
            logger.info("3. Subscribe to newHeads and contract logs")
            logger.info("4. Continue to Phase 1 of WebSocket Migration Plan")
        else:
            logger.info("1. ⚠️  Proceed with Option B/C (Fast Polling)")
            logger.info("2. Implement 2-second HTTP polling with eventlet")
            logger.info("3. Use Flask-SocketIO to push to clients")
            logger.info("4. Continue to Phase 1 of WebSocket Migration Plan")
        
        logger.info("\n")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        logger.info("🚀 Starting Kasplex WebSocket Test Suite")
        logger.info(f"Target: {self.ws_endpoint}\n")
        
        # Test 1: Basic connectivity
        await self.test_websocket_connection()
        
        if not self.results.get('websocket_available'):
            logger.warning("\n⚠️  WebSocket unavailable - skipping advanced tests")
            await self.test_http_fallback()
            self.print_summary()
            return
        
        # Test 2: eth_subscribe support
        await self.test_eth_subscribe_support()
        
        # Test 3: Standard RPC over WebSocket
        await self.test_standard_rpc_methods()
        
        # Test 4: HTTP fallback comparison
        await self.test_http_fallback()
        
        # Test 5: Block time measurement
        await self.measure_block_time()
        
        # Print summary
        self.print_summary()


async def main():
    """Main test runner"""
    tester = KasplexWebSocketTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        logger.error(f"\n\n❌ Test suite failed: {e}")
        raise
