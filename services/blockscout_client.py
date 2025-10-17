"""
Blockscout GraphQL Client for Kasplex zkEVM L2
Handles all blockchain data queries via GraphQL API
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)

# Correct GraphQL endpoint (found from DevTools)
BLOCKSCOUT_GRAPHQL_URL = "https://explorer.testnet.kasplextest.xyz/api/v1/graphql"


class BlockscoutClient:
    """Client for querying Blockscout GraphQL API"""
    
    def __init__(self, graphql_url: str = BLOCKSCOUT_GRAPHQL_URL):
        """Initialize GraphQL client"""
        self.transport = RequestsHTTPTransport(
            url=graphql_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30
        )
        self.client = Client(
            transport=self.transport,
            fetch_schema_from_transport=False  # Skip schema fetch for speed
        )
        logger.info(f"✅ BlockscoutClient initialized: {graphql_url}")
    
    def get_token_transfers(
        self, 
        token_address: str, 
        first: int = 5,
        after: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent token transfers (trades) for a specific token
        
        Args:
            token_address: Token contract address (e.g., 0x...)
            first: Number of transfers to fetch (default 5, max 10 due to complexity limit)
            after: Cursor for pagination
            
        Returns:
            List of transfer events with buyer, seller, amounts, timestamp
            
        Note:
            Blockscout has query complexity limit of 100.
            Each transfer ~10 complexity points, so max ~10 transfers per query.
        """
        # Simplified query to reduce complexity (stays under limit of 100)
        query = gql("""
            query GetTokenTransfers($tokenAddress: AddressHash!, $first: Int!) {
                address(hash: $tokenAddress) {
                    tokenTransfers(first: $first) {
                        edges {
                            node {
                                blockNumber
                                fromAddressHash
                                toAddressHash
                                amount
                                transaction {
                                    hash
                                    value
                                    block {
                                        timestamp
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """)
        
        try:
            variables = {
                "tokenAddress": token_address,
                "first": min(first, 8)  # Cap at 8 to stay under complexity limit (~90 complexity)
            }
                
            result = self.client.execute(query, variable_values=variables)
            
            # Extract and format transfers
            transfers = []
            if result and "address" in result and result["address"]:
                edges = result["address"]["tokenTransfers"]["edges"]
                for edge in edges:
                    node = edge["node"]
                    transfers.append({
                        "buyer": node["toAddressHash"],
                        "seller": node["fromAddressHash"],
                        "token_amount": node.get("amount", "0"),
                        "tx_hash": node["transaction"]["hash"],
                        "block_number": node["blockNumber"],
                        "timestamp": node["transaction"]["block"]["timestamp"],
                        "gas_used": node["transaction"].get("gasUsed"),
                        "kas_value": node["transaction"].get("value", "0")
                    })
            
            logger.info(f"✅ Fetched {len(transfers)} token transfers for {token_address[:10]}...")
            return transfers
            
        except Exception as e:
            logger.error(f"❌ GraphQL query failed: {type(e).__name__}: {str(e)}")
            return []
    
    def get_token_holders(
        self,
        token_address: str,
        min_balance: int = 0,
        first: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get current token holders and their balances
        
        Args:
            token_address: Token contract address
            min_balance: Minimum balance to include (default 0)
            first: Number of holders to fetch
            
        Returns:
            List of {address, balance, percentage}
        """
        # Note: This query structure depends on Blockscout schema
        # May need adjustment based on actual available fields
        query = gql("""
            query GetTokenHolders($tokenAddress: AddressHash!) {
                address(hash: $tokenAddress) {
                    hash
                    tokenBalances(first: 100) {
                        edges {
                            node {
                                address {
                                    hash
                                }
                                value
                            }
                        }
                    }
                }
            }
        """)
        
        try:
            result = self.client.execute(
                query,
                variable_values={"tokenAddress": token_address}
            )
            
            holders = []
            if result and "address" in result and result["address"]:
                edges = result["address"].get("tokenBalances", {}).get("edges", [])
                total_supply = 0
                
                # First pass: calculate total
                for edge in edges:
                    node = edge["node"]
                    balance = int(node.get("value", "0"))
                    if balance >= min_balance:
                        total_supply += balance
                
                # Second pass: calculate percentages
                for edge in edges:
                    node = edge["node"]
                    balance = int(node.get("value", "0"))
                    if balance >= min_balance:
                        holders.append({
                            "address": node["address"]["hash"],
                            "balance": str(balance),
                            "percentage": (balance / total_supply * 100) if total_supply > 0 else 0
                        })
            
            logger.info(f"✅ Fetched {len(holders)} token holders for {token_address[:10]}...")
            return holders
            
        except Exception as e:
            logger.error(f"❌ Get holders failed: {type(e).__name__}: {str(e)}")
            return []
    
    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get single transaction details by hash
        
        Args:
            tx_hash: Transaction hash (0x...)
            
        Returns:
            Transaction details dict or None
        """
        query = gql("""
            query GetTransaction($hash: FullHash!) {
                transaction(hash: $hash) {
                    hash
                    blockNumber
                    fromAddressHash
                    toAddressHash
                    value
                    gasUsed
                    gasPrice
                    status
                    input
                    nonce
                    block {
                        timestamp
                        hash
                    }
                }
            }
        """)
        
        try:
            result = self.client.execute(
                query,
                variable_values={"hash": tx_hash}
            )
            
            if result and "transaction" in result:
                tx = result["transaction"]
                logger.info(f"✅ Fetched transaction {tx_hash[:10]}...")
                return tx
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Get transaction failed: {type(e).__name__}: {str(e)}")
            return None
    
    def get_all_token_transfers(
        self,
        token_address: str,
        max_transfers: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get ALL token transfers for a token.
        
        NOTE: Blockscout GraphQL doesn't support cursor pagination effectively.
        This fetches recent transfers only (up to 8 due to complexity limits).
        For complete history, we rely on the event indexer or accept limitations.
        
        Args:
            token_address: Token contract address (e.g., 0x...)
            max_transfers: Maximum number of transfers to fetch (default 1000, but limited to 8)
            
        Returns:
            List of transfer events sorted by timestamp (oldest first)
        """
        logger.info(f"📊 Fetching transfer history for {token_address[:10]}...")
        
        try:
            # Due to Blockscout complexity limits, we can only fetch ~8 transfers per query
            # and cursor pagination isn't properly supported
            transfers = self.get_token_transfers(
                token_address=token_address,
                first=8  # Max we can reliably fetch
            )
            
            # Sort by timestamp (oldest first) for proper reserve calculation
            transfers.sort(key=lambda x: x.get('timestamp', ''))
            
            logger.info(f"✅ Fetched {len(transfers)} transfers (limited by GraphQL complexity)")
            return transfers
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch transfers: {type(e).__name__}: {str(e)}")
            return []
    
    def health_check(self) -> bool:
        """
        Check if GraphQL API is accessible
        
        Returns:
            True if API is healthy, False otherwise
        """
        query = gql("""
            {
                __schema {
                    queryType {
                        name
                    }
                }
            }
        """)
        
        try:
            result = self.client.execute(query)
            is_healthy = bool(result and "__schema" in result)
            status = "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY"
            logger.info(f"{status} - Blockscout GraphQL API")
            return is_healthy
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {type(e).__name__}: {str(e)}")
            return False


# Global client instance
_client_instance = None

def get_blockscout_client() -> BlockscoutClient:
    """Get or create singleton BlockscoutClient instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = BlockscoutClient()
    return _client_instance
