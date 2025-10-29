"""
Uniswap V3 Quote Calculator
Deterministic quote calculation using pool state and V3 swap math

Does NOT require QuoterV2 contract calls - reads pool state directly
and calculates quotes using the same math as Uniswap V3 core.
"""

import logging
from typing import Tuple, Dict
from web3 import Web3

from services.uniswap_v3_math import (
    TickMath,
    SqrtPriceMath,
    SwapMath,
    FullMath,
    sqrt_price_x96_to_price
)


class UniswapV3Quoter:
    """
    Deterministic V3 quote calculator
    
    Reads pool state and calculates swap quotes using V3 math libraries.
    This replaces QuoterV2 contract calls with direct calculation.
    """
    
    def __init__(self, w3, pool_contract):
        """
        Initialize quoter for a specific V3 pool
        
        Args:
            w3: Web3 instance
            pool_contract: Web3 contract instance of Uniswap V3 pool
        """
        self.w3 = w3
        self.pool = pool_contract
        
        self.token0 = self.pool.functions.token0().call()
        self.token1 = self.pool.functions.token1().call()
        self.fee = self.pool.functions.fee().call()
        
        logging.debug(f"V3 Quoter initialized - Pool: {self.pool.address}, Fee: {self.fee}")
    
    def get_pool_state(self) -> Dict:
        """
        Read current pool state from slot0 and liquidity
        
        Returns:
            dict: {
                'sqrt_price_x96': int,
                'tick': int,
                'liquidity': int,
                'observation_index': int,
                'observation_cardinality': int,
                'observation_cardinality_next': int,
                'fee_protocol': int,
                'unlocked': bool
            }
        """
        try:
            # Manually read slot0() raw bytes (Kaspa Finance pools return non-standard format)
            slot0_data = self.w3.eth.call({
                'to': self.pool.address,
                'data': '0x3850c7bd'  # slot0() function selector
            })
            
            # Parse raw bytes (standard Uniswap V3 layout in first 224 bytes)
            sqrt_price_x96 = int.from_bytes(slot0_data[0:32], 'big')
            tick = int.from_bytes(slot0_data[32:64], 'big', signed=True)
            observation_index = int.from_bytes(slot0_data[64:96], 'big')
            observation_cardinality = int.from_bytes(slot0_data[96:128], 'big')
            observation_cardinality_next = int.from_bytes(slot0_data[128:160], 'big')
            fee_protocol = int.from_bytes(slot0_data[160:192], 'big')
            unlocked = int.from_bytes(slot0_data[192:224], 'big')
            
            # Handle int24 tick properly (convert from int256 to int24)
            if tick > 2**23 - 1:
                tick = tick - 2**24
            
            # Read liquidity normally
            liquidity = self.pool.functions.liquidity().call()
            
            state = {
                'sqrt_price_x96': sqrt_price_x96,
                'tick': tick,
                'observation_index': observation_index,
                'observation_cardinality': observation_cardinality,
                'observation_cardinality_next': observation_cardinality_next,
                'fee_protocol': fee_protocol,
                'unlocked': bool(unlocked),
                'liquidity': liquidity
            }
            
            logging.debug(f"Pool state: sqrtPriceX96={state['sqrt_price_x96']}, tick={state['tick']}, liquidity={state['liquidity']}")
            return state
            
        except Exception as e:
            logging.error(f"Failed to read pool state: {str(e)}")
            raise
    
    def quote_exact_input_single(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        sqrt_price_limit_x96: int = 0
    ) -> Tuple[int, int, int]:
        """
        Calculate quote for exact input swap (single pool)
        
        This mimics QuoterV2.quoteExactInputSingle() but uses pure math.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount (in wei)
            sqrt_price_limit_x96: Price limit (0 = no limit)
        
        Returns:
            Tuple of (amount_out, sqrt_price_after_x96, gas_estimate)
        """
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            zero_for_one = token_in.lower() == self.token0.lower()
            
            if not zero_for_one and token_in.lower() != self.token1.lower():
                raise ValueError(f"Token {token_in} not in pool")
            
            state = self.get_pool_state()
            sqrt_price_current_x96 = state['sqrt_price_x96']
            liquidity = state['liquidity']
            
            if sqrt_price_limit_x96 == 0:
                sqrt_price_limit_x96 = (
                    TickMath.MIN_SQRT_RATIO + 1 if zero_for_one
                    else TickMath.MAX_SQRT_RATIO - 1
                )
            
            if liquidity == 0:
                raise ValueError("Pool has no liquidity")
            
            sqrt_ratio_next_x96, amount_in_calc, amount_out, fee_amount = SwapMath.compute_swap_step(
                sqrt_price_current_x96,
                sqrt_price_limit_x96,
                liquidity,
                amount_in,
                self.fee
            )
            
            gas_estimate = 150000
            
            logging.info(f"V3 Quote (Exact Input): {amount_in} in → {amount_out} out (fee: {fee_amount})")
            return (amount_out, sqrt_ratio_next_x96, gas_estimate)
            
        except Exception as e:
            logging.error(f"Failed to quote exact input: {str(e)}")
            raise
    
    def quote_exact_output_single(
        self,
        token_in: str,
        token_out: str,
        amount_out: int,
        sqrt_price_limit_x96: int = 0
    ) -> Tuple[int, int, int]:
        """
        Calculate quote for exact output swap (single pool)
        
        This mimics QuoterV2.quoteExactOutputSingle() but uses pure math.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_out: Desired output amount (in wei)
            sqrt_price_limit_x96: Price limit (0 = no limit)
        
        Returns:
            Tuple of (amount_in, sqrt_price_after_x96, gas_estimate)
        """
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            zero_for_one = token_in.lower() == self.token0.lower()
            
            if not zero_for_one and token_in.lower() != self.token1.lower():
                raise ValueError(f"Token {token_in} not in pool")
            
            state = self.get_pool_state()
            sqrt_price_current_x96 = state['sqrt_price_x96']
            liquidity = state['liquidity']
            
            if sqrt_price_limit_x96 == 0:
                sqrt_price_limit_x96 = (
                    TickMath.MIN_SQRT_RATIO + 1 if zero_for_one
                    else TickMath.MAX_SQRT_RATIO - 1
                )
            
            if liquidity == 0:
                raise ValueError("Pool has no liquidity")
            
            sqrt_ratio_next_x96, amount_in, amount_out_calc, fee_amount = SwapMath.compute_swap_step(
                sqrt_price_current_x96,
                sqrt_price_limit_x96,
                liquidity,
                -amount_out,
                self.fee
            )
            
            gas_estimate = 150000
            
            logging.info(f"V3 Quote (Exact Output): {amount_in} in needed → {amount_out} out (fee: {fee_amount})")
            return (amount_in, sqrt_ratio_next_x96, gas_estimate)
            
        except Exception as e:
            logging.error(f"Failed to quote exact output: {str(e)}")
            raise
    
    def get_spot_price(self, decimals0: int = 18, decimals1: int = 18) -> float:
        """
        Get current spot price from pool state
        
        Args:
            decimals0: Token0 decimals
            decimals1: Token1 decimals
        
        Returns:
            Price as float (token1 per token0)
        """
        try:
            state = self.get_pool_state()
            sqrt_price_x96 = state['sqrt_price_x96']
            
            price = sqrt_price_x96_to_price(sqrt_price_x96, decimals0, decimals1)
            
            logging.debug(f"Spot price: {price} (token1 per token0)")
            return price
            
        except Exception as e:
            logging.error(f"Failed to get spot price: {str(e)}")
            raise
    
    def calculate_price_impact(
        self,
        sqrt_price_before_x96: int,
        sqrt_price_after_x96: int
    ) -> float:
        """
        Calculate price impact percentage
        
        Args:
            sqrt_price_before_x96: Price before swap
            sqrt_price_after_x96: Price after swap
        
        Returns:
            Price impact as percentage (e.g., 0.5 for 0.5%)
        """
        try:
            price_before = (sqrt_price_before_x96 / (2 ** 96)) ** 2
            price_after = (sqrt_price_after_x96 / (2 ** 96)) ** 2
            
            if price_before == 0:
                return 0.0
            
            price_impact_percent = abs((price_after - price_before) / price_before) * 100
            
            return price_impact_percent
            
        except Exception as e:
            logging.error(f"Failed to calculate price impact: {str(e)}")
            return 0.0


def create_quoter_for_pool(w3, pool_address: str) -> UniswapV3Quoter:
    """
    Create a quoter instance for a specific V3 pool
    
    Args:
        w3: Web3 instance
        pool_address: Address of Uniswap V3 pool
    
    Returns:
        UniswapV3Quoter instance
    """
    try:
        from pathlib import Path
        import json
        
        artifacts_dir = Path("artifacts/contracts")
        pool_abi_path = artifacts_dir / "interfaces" / "IUniswapV3Pool.sol" / "IUniswapV3Pool.json"
        
        if not pool_abi_path.exists():
            raise FileNotFoundError(f"IUniswapV3Pool ABI not found at {pool_abi_path}")
        
        with open(pool_abi_path, 'r') as f:
            pool_abi = json.load(f)['abi']
        
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=pool_abi
        )
        
        return UniswapV3Quoter(w3, pool_contract)
        
    except Exception as e:
        logging.error(f"Failed to create quoter for pool {pool_address}: {str(e)}")
        raise


def calculate_exact_input_quote(
    w3,
    pool_address: str,
    token_in: str,
    token_out: str,
    amount_in: int,
    fee: int
) -> Dict:
    """
    Calculate quote for exact input swap
    
    Standalone function for easy integration with web3_service.py
    
    Args:
        w3: Web3 instance
        pool_address: Address of V3 pool
        token_in: Input token address
        token_out: Output token address
        amount_in: Input amount (wei)
        fee: Fee tier (e.g., 2500 for 0.25%)
    
    Returns:
        dict: {
            'amount_out': int,
            'sqrt_price_after_x96': int,
            'gas_estimate': int,
            'price_impact_percent': float
        }
    """
    try:
        quoter = create_quoter_for_pool(w3, pool_address)
        
        state_before = quoter.get_pool_state()
        sqrt_price_before = state_before['sqrt_price_x96']
        
        amount_out, sqrt_price_after, gas_estimate = quoter.quote_exact_input_single(
            token_in,
            token_out,
            amount_in,
            0
        )
        
        price_impact = quoter.calculate_price_impact(sqrt_price_before, sqrt_price_after)
        
        return {
            'amount_out': amount_out,
            'sqrt_price_after_x96': sqrt_price_after,
            'gas_estimate': gas_estimate,
            'price_impact_percent': price_impact
        }
        
    except Exception as e:
        logging.error(f"Failed to calculate exact input quote: {str(e)}")
        raise


def calculate_exact_output_quote(
    w3,
    pool_address: str,
    token_in: str,
    token_out: str,
    amount_out: int,
    fee: int
) -> Dict:
    """
    Calculate quote for exact output swap
    
    Standalone function for easy integration with web3_service.py
    
    Args:
        w3: Web3 instance
        pool_address: Address of V3 pool
        token_in: Input token address
        token_out: Output token address
        amount_out: Desired output amount (wei)
        fee: Fee tier (e.g., 2500 for 0.25%)
    
    Returns:
        dict: {
            'amount_in': int,
            'sqrt_price_after_x96': int,
            'gas_estimate': int,
            'price_impact_percent': float
        }
    """
    try:
        quoter = create_quoter_for_pool(w3, pool_address)
        
        state_before = quoter.get_pool_state()
        sqrt_price_before = state_before['sqrt_price_x96']
        
        amount_in, sqrt_price_after, gas_estimate = quoter.quote_exact_output_single(
            token_in,
            token_out,
            amount_out,
            0
        )
        
        price_impact = quoter.calculate_price_impact(sqrt_price_before, sqrt_price_after)
        
        return {
            'amount_in': amount_in,
            'sqrt_price_after_x96': sqrt_price_after,
            'gas_estimate': gas_estimate,
            'price_impact_percent': price_impact
        }
        
    except Exception as e:
        logging.error(f"Failed to calculate exact output quote: {str(e)}")
        raise
