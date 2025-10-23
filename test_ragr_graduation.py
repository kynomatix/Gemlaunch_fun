"""
RAGR Token Graduation Test Script
Execute graduation and capture all metrics for verification
"""

import sys
import json
import time
from datetime import datetime
from app import app, db
from models import Token
from services.web3_service import get_web3_service

def main():
    """Execute RAGR graduation and capture all results"""
    
    print("=" * 80)
    print("RAGR TOKEN GRADUATION TEST")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Initialize
    w3_service = get_web3_service()
    ragr_address = "0xa75c9441ba642165df45fbcdb03b5627521ecb7a"
    
    results = {
        "token_address": ragr_address,
        "test_start_time": datetime.now().isoformat(),
        "phases": {}
    }
    
    with app.app_context():
        # Get token from database
        token = Token.query.filter_by(contract_address=ragr_address.lower()).first()
        
        if not token:
            print(f"❌ ERROR: Token {ragr_address} not found in database")
            return
        
        print(f"✅ Found token: {token.symbol} ({token.name})")
        print(f"   Current status: {token.graduation_status}")
        print(f"   Contract: {token.contract_address}")
        print()
        
        # Check if we need to initiate first
        if token.graduation_status == 'active':
            print("⚠️ Token is in 'active' status - need to initiate graduation first")
            print()
            print("=" * 80)
            print("PHASE 0: INITIATE GRADUATION")
            print("=" * 80)
            
            try:
                print(f"Calling initiate_graduation_oracle('{ragr_address}')...")
                initiate_result = w3_service.initiate_graduation_oracle(ragr_address)
                
                results["phases"]["phase0_initiation"] = {
                    "success": True,
                    "tx_hash": initiate_result.get("tx_hash"),
                    "gas_used": initiate_result.get("gas_used"),
                    "status": initiate_result.get("status")
                }
                
                print(f"✅ Initiation tx sent: {initiate_result.get('tx_hash')}")
                print(f"   Gas used: {initiate_result.get('gas_used')}")
                print(f"   Waiting for confirmation...")
                
                # Wait a bit for status update
                time.sleep(5)
                db.session.refresh(token)
                
                print(f"   New status: {token.graduation_status}")
                print()
                
            except Exception as e:
                print(f"❌ ERROR initiating: {str(e)}")
                results["phases"]["phase0_initiation"] = {
                    "success": False,
                    "error": str(e)
                }
                # Don't continue if initiation failed
                with open('ragr_graduation_test_results.json', 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                return
        
        # =================================================================
        # PHASE 1: Execute Graduation Completion
        # =================================================================
        print("=" * 80)
        print("PHASE 1: TRIGGER GRADUATION COMPLETION")
        print("=" * 80)
        
        try:
            print(f"Calling complete_graduation_oracle('{ragr_address}')...")
            result = w3_service.complete_graduation_oracle(ragr_address)
            
            results["phases"]["phase1_execution"] = {
                "success": True,
                "tx_hash": result.get("tx_hash"),
                "gas_used": result.get("gas_used"),
                "gas_price": result.get("gas_price"),
                "status": result.get("status"),
                "error": None
            }
            
            print(f"✅ Transaction sent: {result.get('tx_hash')}")
            print(f"   Gas used: {result.get('gas_used')}")
            print(f"   Gas price: {result.get('gas_price')}")
            print(f"   Status: {result.get('status')}")
            print()
            
            # Get full receipt
            tx_hash = result.get("tx_hash")
            if tx_hash:
                receipt = w3_service.w3.eth.get_transaction_receipt(tx_hash)
                results["phases"]["phase1_execution"]["receipt"] = {
                    "blockNumber": receipt.get("blockNumber"),
                    "gasUsed": receipt.get("gasUsed"),
                    "effectiveGasPrice": receipt.get("effectiveGasPrice"),
                    "status": receipt.get("status"),
                    "logs_count": len(receipt.get("logs", []))
                }
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            results["phases"]["phase1_execution"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            receipt = None
        
        # =================================================================
        # PHASE 2: Parse Transaction Events
        # =================================================================
        print("=" * 80)
        print("PHASE 2: PARSE TRANSACTION EVENTS")
        print("=" * 80)
        
        if receipt and receipt.get("status") == 1:
            try:
                events_found = {
                    "GraduationCompleted": None,
                    "PoolCreated": None,
                    "Mint": None
                }
                
                # Parse GraduationCompleted event
                graduation_controller = w3_service.contracts['GraduationController']
                grad_event = graduation_controller.events.GraduationCompleted()
                
                for log in receipt['logs']:
                    try:
                        decoded = grad_event.process_log(log)
                        if decoded['args']['tokenAddress'].lower() == ragr_address.lower():
                            events_found["GraduationCompleted"] = {
                                "tokenAddress": decoded['args']['tokenAddress'],
                                "liquidityPositionId": decoded['args']['liquidityPositionId'],
                                "kasAdded": decoded['args']['kasAdded'],
                                "tokensAdded": decoded['args']['tokensAdded'],
                                "timestamp": decoded['args']['timestamp']
                            }
                            print(f"✅ GraduationCompleted event found:")
                            print(f"   Position ID: {decoded['args']['liquidityPositionId']}")
                            print(f"   KAS Added: {w3_service.w3.from_wei(decoded['args']['kasAdded'], 'ether')} KAS")
                            print(f"   Tokens Added: {decoded['args']['tokensAdded']}")
                            break
                    except:
                        continue
                
                # Look for PoolCreated and Mint events in logs
                print()
                print("📋 All transaction logs:")
                for i, log in enumerate(receipt['logs']):
                    print(f"   Log {i}: {log['address']}")
                    print(f"      Topics: {len(log['topics'])}")
                    if log['topics']:
                        print(f"      Topic[0]: {log['topics'][0].hex()}")
                
                results["phases"]["phase2_events"] = {
                    "success": True,
                    "events_found": events_found,
                    "total_logs": len(receipt['logs'])
                }
                
            except Exception as e:
                print(f"❌ ERROR parsing events: {str(e)}")
                import traceback
                traceback.print_exc()
                results["phases"]["phase2_events"] = {
                    "success": False,
                    "error": str(e)
                }
        else:
            print("⚠️ No receipt available or transaction failed")
            results["phases"]["phase2_events"] = {
                "success": False,
                "error": "No receipt or tx failed"
            }
        
        print()
        
        # =================================================================
        # PHASE 3: Verify On-Chain State
        # =================================================================
        print("=" * 80)
        print("PHASE 3: VERIFY ON-CHAIN STATE")
        print("=" * 80)
        
        # Wait a bit for DB updates
        time.sleep(3)
        
        try:
            # Refresh token from DB
            db.session.refresh(token)
            
            if token.dex_pool_address:
                pool_address = token.dex_pool_address
                print(f"Pool address from DB: {pool_address}")
                
                # Get pool contract (Uniswap V3 pool ABI)
                pool_abi = [
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                            {"internalType": "int24", "name": "tick", "type": "int24"},
                            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                            {"internalType": "bool", "name": "unlocked", "type": "bool"}
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [],
                        "name": "liquidity",
                        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                
                pool = w3_service.w3.eth.contract(
                    address=w3_service.w3.to_checksum_address(pool_address),
                    abi=pool_abi
                )
                
                # Get slot0
                slot0 = pool.functions.slot0().call()
                sqrtPriceX96 = slot0[0]
                tick = slot0[1]
                
                print(f"✅ Pool slot0:")
                print(f"   sqrtPriceX96: {sqrtPriceX96:,}")
                print(f"   tick: {tick}")
                print(f"   Expected sqrtPriceX96: ~17,570,824,045,140,000")
                
                # Get liquidity
                liquidity = pool.functions.liquidity().call()
                print(f"✅ Pool liquidity: {liquidity:,}")
                
                results["phases"]["phase3_onchain"] = {
                    "success": True,
                    "pool_address": pool_address,
                    "sqrtPriceX96": sqrtPriceX96,
                    "tick": tick,
                    "liquidity": liquidity,
                    "price_matches_expected": abs(sqrtPriceX96 - 17570824045140000) < 1e15
                }
                
            else:
                print("⚠️ No DEX pool address in database yet")
                results["phases"]["phase3_onchain"] = {
                    "success": False,
                    "error": "No pool address in DB"
                }
                
        except Exception as e:
            print(f"❌ ERROR verifying on-chain state: {str(e)}")
            import traceback
            traceback.print_exc()
            results["phases"]["phase3_onchain"] = {
                "success": False,
                "error": str(e)
            }
        
        print()
        
        # =================================================================
        # PHASE 4: Verify Database State
        # =================================================================
        print("=" * 80)
        print("PHASE 4: VERIFY DATABASE STATE")
        print("=" * 80)
        
        try:
            db.session.refresh(token)
            
            print(f"Token: {token.symbol}")
            print(f"   graduation_status: {token.graduation_status}")
            print(f"   dex_pool_address: {token.dex_pool_address}")
            print(f"   lp_nft_position_id: {token.lp_nft_position_id}")
            print(f"   dex_pool_fee_tier: {token.dex_pool_fee_tier}")
            print(f"   graduation_completed_at: {token.graduation_completed_at}")
            print(f"   graduation_completion_tx: {token.graduation_completion_tx}")
            print(f"   is_graduated (legacy): {token.is_graduated}")
            
            results["phases"]["phase4_database"] = {
                "success": True,
                "graduation_status": token.graduation_status,
                "dex_pool_address": token.dex_pool_address,
                "lp_nft_position_id": token.lp_nft_position_id,
                "dex_pool_fee_tier": token.dex_pool_fee_tier,
                "graduation_completed_at": str(token.graduation_completed_at) if token.graduation_completed_at else None,
                "graduation_completion_tx": token.graduation_completion_tx,
                "is_graduated": token.is_graduated,
                "status_is_graduated": token.graduation_status == 'graduated',
                "pool_address_present": bool(token.dex_pool_address),
                "position_id_present": bool(token.lp_nft_position_id)
            }
            
        except Exception as e:
            print(f"❌ ERROR verifying database: {str(e)}")
            results["phases"]["phase4_database"] = {
                "success": False,
                "error": str(e)
            }
        
        print()
        
        # =================================================================
        # SUMMARY
        # =================================================================
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        results["test_end_time"] = datetime.now().isoformat()
        results["summary"] = {
            "phase1_success": results["phases"].get("phase1_execution", {}).get("success", False),
            "phase2_success": results["phases"].get("phase2_events", {}).get("success", False),
            "phase3_success": results["phases"].get("phase3_onchain", {}).get("success", False),
            "phase4_success": results["phases"].get("phase4_database", {}).get("success", False),
            "overall_success": all([
                results["phases"].get("phase1_execution", {}).get("success", False),
                results["phases"].get("phase2_events", {}).get("success", False),
                results["phases"].get("phase3_onchain", {}).get("success", False),
                results["phases"].get("phase4_database", {}).get("success", False)
            ])
        }
        
        for phase, data in results["phases"].items():
            status = "✅" if data.get("success") else "❌"
            print(f"{status} {phase}: {data.get('success', False)}")
        
        print()
        print(f"Overall: {'✅ SUCCESS' if results['summary']['overall_success'] else '❌ FAILED'}")
        
        # Save results to JSON
        with open('ragr_graduation_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print()
        print("Results saved to: ragr_graduation_test_results.json")
        
        return results

if __name__ == "__main__":
    main()
