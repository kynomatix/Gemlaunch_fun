"""
Uniswap V3 Math Libraries in Python
Implements core V3 swap math for deterministic quote calculation

References:
- https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/
- https://docs.uniswap.org/contracts/v3/reference/core/libraries/
"""

import math
import logging
from decimal import Decimal, getcontext

getcontext().prec = 78


class FullMath:
    """
    Safe multiplication and division helpers
    Ported from Uniswap V3 FullMath.sol
    """
    
    @staticmethod
    def mul_div(a: int, b: int, denominator: int) -> int:
        """
        Calculates floor(a×b÷denominator) with full precision
        Equivalent to Solidity's mulDiv
        
        Args:
            a: Multiplicand
            b: Multiplier  
            denominator: Divisor
        
        Returns:
            Result of a * b / denominator (floor division)
        """
        if denominator == 0:
            raise ValueError("Division by zero")
        
        result = (a * b) // denominator
        return result
    
    @staticmethod
    def mul_div_rounding_up(a: int, b: int, denominator: int) -> int:
        """
        Calculates ceil(a×b÷denominator) with full precision
        Used when rounding should favor the pool
        
        Args:
            a: Multiplicand
            b: Multiplier
            denominator: Divisor
        
        Returns:
            Result of a * b / denominator (ceiling division)
        """
        if denominator == 0:
            raise ValueError("Division by zero")
        
        result = (a * b + denominator - 1) // denominator
        return result


class TickMath:
    """
    Tick <-> sqrtPriceX96 conversions
    Ported from Uniswap V3 TickMath.sol
    
    Key concept: tick = floor(log_1.0001(price))
    sqrtPriceX96 = sqrt(1.0001^tick) * 2^96
    """
    
    MIN_TICK = -887272
    MAX_TICK = 887272
    MIN_SQRT_RATIO = 4295128739
    MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
    
    Q96 = 2 ** 96
    
    @staticmethod
    def get_sqrt_ratio_at_tick(tick: int) -> int:
        """
        Convert tick to sqrtPriceX96
        
        Formula: sqrtPriceX96 = sqrt(1.0001^tick) * 2^96
        
        Args:
            tick: Tick value
        
        Returns:
            sqrtPriceX96 (uint160)
        """
        if tick < TickMath.MIN_TICK or tick > TickMath.MAX_TICK:
            raise ValueError(f"Tick {tick} out of bounds")
        
        abs_tick = abs(tick)
        
        ratio = 0xfffcb933bd6fad37aa2d162d1a594001 if abs_tick & 0x1 else 0x100000000000000000000000000000000
        if abs_tick & 0x2:
            ratio = (ratio * 0xfff97272373d413259a46990580e213a) >> 128
        if abs_tick & 0x4:
            ratio = (ratio * 0xfff2e50f5f656932ef12357cf3c7fdcc) >> 128
        if abs_tick & 0x8:
            ratio = (ratio * 0xffe5caca7e10e4e61c3624eaa0941cd0) >> 128
        if abs_tick & 0x10:
            ratio = (ratio * 0xffcb9843d60f6159c9db58835c926644) >> 128
        if abs_tick & 0x20:
            ratio = (ratio * 0xff973b41fa98c081472e6896dfb254c0) >> 128
        if abs_tick & 0x40:
            ratio = (ratio * 0xff2ea16466c96a3843ec78b326b52861) >> 128
        if abs_tick & 0x80:
            ratio = (ratio * 0xfe5dee046a99a2a811c461f1969c3053) >> 128
        if abs_tick & 0x100:
            ratio = (ratio * 0xfcbe86c7900a88aedcffc83b479aa3a4) >> 128
        if abs_tick & 0x200:
            ratio = (ratio * 0xf987a7253ac413176f2b074cf7815e54) >> 128
        if abs_tick & 0x400:
            ratio = (ratio * 0xf3392b0822b70005940c7a398e4b70f3) >> 128
        if abs_tick & 0x800:
            ratio = (ratio * 0xe7159475a2c29b7443b29c7fa6e889d9) >> 128
        if abs_tick & 0x1000:
            ratio = (ratio * 0xd097f3bdfd2022b8845ad8f792aa5825) >> 128
        if abs_tick & 0x2000:
            ratio = (ratio * 0xa9f746462d870fdf8a65dc1f90e061e5) >> 128
        if abs_tick & 0x4000:
            ratio = (ratio * 0x70d869a156d2a1b890bb3df62baf32f7) >> 128
        if abs_tick & 0x8000:
            ratio = (ratio * 0x31be135f97d08fd981231505542fcfa6) >> 128
        if abs_tick & 0x10000:
            ratio = (ratio * 0x9aa508b5b7a84e1c677de54f3e99bc9) >> 128
        if abs_tick & 0x20000:
            ratio = (ratio * 0x5d6af8dedb81196699c329225ee604) >> 128
        if abs_tick & 0x40000:
            ratio = (ratio * 0x2216e584f5fa1ea926041bedfe98) >> 128
        if abs_tick & 0x80000:
            ratio = (ratio * 0x48a170391f7dc42444e8fa2) >> 128
        
        if tick > 0:
            ratio = (2 ** 256 - 1) // ratio
        
        return (ratio >> 32) + (0 if ratio % (1 << 32) == 0 else 1)
    
    @staticmethod
    def get_tick_at_sqrt_ratio(sqrt_price_x96: int) -> int:
        """
        Convert sqrtPriceX96 to tick
        
        Formula: tick = floor(log_1.0001(price))
                      = floor(log_1.0001((sqrtPriceX96 / 2^96)^2))
        
        Args:
            sqrt_price_x96: Square root price in Q64.96 format
        
        Returns:
            Tick value
        """
        if sqrt_price_x96 < TickMath.MIN_SQRT_RATIO or sqrt_price_x96 >= TickMath.MAX_SQRT_RATIO:
            raise ValueError(f"sqrtPriceX96 {sqrt_price_x96} out of bounds")
        
        ratio = sqrt_price_x96 << 32
        
        r = ratio
        msb = 0
        
        f = (r > 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF) << 7
        msb = msb | f
        r = r >> f
        
        f = (r > 0xFFFFFFFFFFFFFFFF) << 6
        msb = msb | f
        r = r >> f
        
        f = (r > 0xFFFFFFFF) << 5
        msb = msb | f
        r = r >> f
        
        f = (r > 0xFFFF) << 4
        msb = msb | f
        r = r >> f
        
        f = (r > 0xFF) << 3
        msb = msb | f
        r = r >> f
        
        f = (r > 0xF) << 2
        msb = msb | f
        r = r >> f
        
        f = (r > 0x3) << 1
        msb = msb | f
        r = r >> f
        
        f = r > 0x1
        msb = msb | f
        
        if msb >= 128:
            r = ratio >> (msb - 127)
        else:
            r = ratio << (127 - msb)
        
        log_2 = (msb - 128) << 64
        
        for i in range(14):
            r = (r * r) >> 127
            f = r >> 128
            log_2 = log_2 | (f << (63 - i))
            r = r >> f
        
        log_sqrt10001 = log_2 * 255738958999603826347141
        
        tick_low = (log_sqrt10001 - 3402992956809132418596140100660247210) >> 128
        tick_high = (log_sqrt10001 + 291339464771989622907027621153398088495) >> 128
        
        if tick_low == tick_high:
            return tick_low
        else:
            return tick_low if TickMath.get_sqrt_ratio_at_tick(tick_high) <= sqrt_price_x96 else tick_high


class SqrtPriceMath:
    """
    Calculate next sqrt price and amount deltas
    Ported from Uniswap V3 SqrtPriceMath.sol
    """
    
    @staticmethod
    def get_next_sqrt_price_from_input(
        sqrt_price_x96: int,
        liquidity: int,
        amount_in: int,
        zero_for_one: bool
    ) -> int:
        """
        Calculate next sqrt price given input amount
        
        Args:
            sqrt_price_x96: Current sqrt price
            liquidity: Available liquidity
            amount_in: Input amount
            zero_for_one: True if selling token0 for token1
        
        Returns:
            Next sqrt price (uint160)
        """
        if sqrt_price_x96 <= 0 or liquidity <= 0:
            raise ValueError("Invalid sqrt price or liquidity")
        
        if zero_for_one:
            return SqrtPriceMath._get_next_sqrt_price_from_amount0_rounding_up(
                sqrt_price_x96, liquidity, amount_in, True
            )
        else:
            return SqrtPriceMath._get_next_sqrt_price_from_amount1_rounding_down(
                sqrt_price_x96, liquidity, amount_in, True
            )
    
    @staticmethod
    def get_next_sqrt_price_from_output(
        sqrt_price_x96: int,
        liquidity: int,
        amount_out: int,
        zero_for_one: bool
    ) -> int:
        """
        Calculate next sqrt price given output amount
        
        Args:
            sqrt_price_x96: Current sqrt price
            liquidity: Available liquidity
            amount_out: Output amount
            zero_for_one: True if selling token0 for token1
        
        Returns:
            Next sqrt price (uint160)
        """
        if sqrt_price_x96 <= 0 or liquidity <= 0:
            raise ValueError("Invalid sqrt price or liquidity")
        
        if zero_for_one:
            return SqrtPriceMath._get_next_sqrt_price_from_amount1_rounding_down(
                sqrt_price_x96, liquidity, amount_out, False
            )
        else:
            return SqrtPriceMath._get_next_sqrt_price_from_amount0_rounding_up(
                sqrt_price_x96, liquidity, amount_out, False
            )
    
    @staticmethod
    def _get_next_sqrt_price_from_amount0_rounding_up(
        sqrt_price_x96: int,
        liquidity: int,
        amount: int,
        add: bool
    ) -> int:
        """
        Calculate next sqrt price from amount0 (rounding up)
        
        Formula: 
        - add: sqrtP' = liquidity * sqrtP / (liquidity + amount * sqrtP / 2^96)
        - subtract: sqrtP' = liquidity * sqrtP / (liquidity - amount * sqrtP / 2^96)
        """
        if amount == 0:
            return sqrt_price_x96
        
        # Avoid overflow: don't compute (liquidity << 96) directly
        # Instead, work with the formula algebraically
        
        if add:
            product = amount * sqrt_price_x96
            if product // amount == sqrt_price_x96:
                # Formula: (L * 2^96 * sqrtP) / (L * 2^96 + amount * sqrtP)
                # Factor out 2^96: (L * sqrtP) / (L + amount * sqrtP / 2^96)
                # Rewrite: (L * 2^96 * sqrtP) / (L * 2^96 + amount * sqrtP)
                # Use mulDiv: mulDiv(L, sqrtP, L + mulDiv(amount, sqrtP, 2^96))
                product_scaled = FullMath.mul_div(amount, sqrt_price_x96, TickMath.Q96)
                denominator = liquidity + product_scaled
                return FullMath.mul_div_rounding_up(liquidity, sqrt_price_x96, denominator)
            
            # Fallback for overflow case
            # sqrtP' = (L * 2^96) / ((L * 2^96) / sqrtP + amount)
            #        = (L * 2^96) / (L * 2^96 / sqrtP + amount)
            #        = L / (L / sqrtP + amount / 2^96)
            return FullMath.mul_div_rounding_up(
                liquidity,
                TickMath.Q96,
                FullMath.mul_div(liquidity, TickMath.Q96, sqrt_price_x96) + amount
            )
        else:
            product = amount * sqrt_price_x96
            if product // amount != sqrt_price_x96:
                raise ValueError("Amount too large")
            
            # Formula: (L * 2^96 * sqrtP) / (L * 2^96 - amount * sqrtP)
            # Rewrite: (L * sqrtP) / (L - amount * sqrtP / 2^96)
            product_scaled = FullMath.mul_div(amount, sqrt_price_x96, TickMath.Q96)
            if liquidity <= product_scaled:
                raise ValueError("Insufficient liquidity")
            denominator = liquidity - product_scaled
            return FullMath.mul_div_rounding_up(liquidity, sqrt_price_x96, denominator)
    
    @staticmethod
    def _get_next_sqrt_price_from_amount1_rounding_down(
        sqrt_price_x96: int,
        liquidity: int,
        amount: int,
        add: bool
    ) -> int:
        """
        Calculate next sqrt price from amount1 (rounding down)
        
        Formula:
        - add: sqrtP' = sqrtP + amount * 2^96 / liquidity
        - subtract: sqrtP' = sqrtP - amount * 2^96 / liquidity
        """
        if add:
            # Always use mulDiv to avoid overflow
            quotient = FullMath.mul_div(amount, TickMath.Q96, liquidity)
            return sqrt_price_x96 + quotient
        else:
            # Always use mulDiv to avoid overflow
            quotient = FullMath.mul_div_rounding_up(amount, TickMath.Q96, liquidity)
            if sqrt_price_x96 <= quotient:
                raise ValueError("Insufficient liquidity")
            return sqrt_price_x96 - quotient
    
    @staticmethod
    def get_amount0_delta(
        sqrt_ratio_a_x96: int,
        sqrt_ratio_b_x96: int,
        liquidity: int,
        round_up: bool
    ) -> int:
        """
        Calculate amount0 delta for a price range
        
        Formula: amount0 = liquidity * (sqrtB - sqrtA) / (sqrtA * sqrtB)
        
        Args:
            sqrt_ratio_a_x96: Lower sqrt price
            sqrt_ratio_b_x96: Upper sqrt price
            liquidity: Liquidity amount
            round_up: Whether to round up
        
        Returns:
            Amount of token0
        """
        if sqrt_ratio_a_x96 > sqrt_ratio_b_x96:
            sqrt_ratio_a_x96, sqrt_ratio_b_x96 = sqrt_ratio_b_x96, sqrt_ratio_a_x96
        
        numerator2 = sqrt_ratio_b_x96 - sqrt_ratio_a_x96
        
        if sqrt_ratio_a_x96 <= 0:
            raise ValueError("Invalid sqrt price")
        
        # Avoid overflow by using mulDiv instead of bit shift
        # Original: (liquidity << 96) * numerator2 / sqrtB / sqrtA
        # Rewritten: mulDiv(mulDiv(liquidity * 2^96, numerator2, sqrtB), 1, sqrtA)
        # But liquidity * 2^96 still overflows, so we combine into one mulDiv per operation
        
        if round_up:
            # Step 1: (liquidity * numerator2 * 2^96) / sqrtB
            intermediate = FullMath.mul_div_rounding_up(
                FullMath.mul_div_rounding_up(liquidity, numerator2, 1),
                TickMath.Q96,
                sqrt_ratio_b_x96
            )
            # Step 2: intermediate / sqrtA
            return FullMath.mul_div_rounding_up(intermediate, 1, sqrt_ratio_a_x96)
        else:
            # Step 1: (liquidity * numerator2 * 2^96) / sqrtB
            intermediate = FullMath.mul_div(
                FullMath.mul_div(liquidity, numerator2, 1),
                TickMath.Q96,
                sqrt_ratio_b_x96
            )
            # Step 2: intermediate / sqrtA
            return FullMath.mul_div(intermediate, 1, sqrt_ratio_a_x96)
    
    @staticmethod
    def get_amount1_delta(
        sqrt_ratio_a_x96: int,
        sqrt_ratio_b_x96: int,
        liquidity: int,
        round_up: bool
    ) -> int:
        """
        Calculate amount1 delta for a price range
        
        Formula: amount1 = liquidity * (sqrtB - sqrtA)
        
        Args:
            sqrt_ratio_a_x96: Lower sqrt price
            sqrt_ratio_b_x96: Upper sqrt price
            liquidity: Liquidity amount
            round_up: Whether to round up
        
        Returns:
            Amount of token1
        """
        if sqrt_ratio_a_x96 > sqrt_ratio_b_x96:
            sqrt_ratio_a_x96, sqrt_ratio_b_x96 = sqrt_ratio_b_x96, sqrt_ratio_a_x96
        
        if round_up:
            return FullMath.mul_div_rounding_up(liquidity, sqrt_ratio_b_x96 - sqrt_ratio_a_x96, TickMath.Q96)
        else:
            return FullMath.mul_div(liquidity, sqrt_ratio_b_x96 - sqrt_ratio_a_x96, TickMath.Q96)


class SwapMath:
    """
    Compute swap amounts within a single tick range
    Ported from Uniswap V3 SwapMath.sol
    """
    
    @staticmethod
    def compute_swap_step(
        sqrt_ratio_current_x96: int,
        sqrt_ratio_target_x96: int,
        liquidity: int,
        amount_remaining: int,
        fee_pips: int
    ) -> tuple:
        """
        Compute swap step within a single tick range
        
        Args:
            sqrt_ratio_current_x96: Current sqrt price
            sqrt_ratio_target_x96: Target sqrt price (tick boundary)
            liquidity: Available liquidity
            amount_remaining: Amount left to swap (positive for exactIn, negative for exactOut)
            fee_pips: Fee in hundredths of a bip (e.g., 3000 for 0.3%)
        
        Returns:
            Tuple of (sqrt_ratio_next_x96, amount_in, amount_out, fee_amount)
        """
        zero_for_one = sqrt_ratio_current_x96 >= sqrt_ratio_target_x96
        exact_in = amount_remaining >= 0
        
        if exact_in:
            amount_remaining_less_fee = FullMath.mul_div(
                amount_remaining,
                1000000 - fee_pips,
                1000000
            )
            
            if zero_for_one:
                amount_in = SqrtPriceMath.get_amount0_delta(
                    sqrt_ratio_target_x96,
                    sqrt_ratio_current_x96,
                    liquidity,
                    True
                )
            else:
                amount_in = SqrtPriceMath.get_amount1_delta(
                    sqrt_ratio_current_x96,
                    sqrt_ratio_target_x96,
                    liquidity,
                    True
                )
            
            if amount_remaining_less_fee >= amount_in:
                sqrt_ratio_next_x96 = sqrt_ratio_target_x96
            else:
                sqrt_ratio_next_x96 = SqrtPriceMath.get_next_sqrt_price_from_input(
                    sqrt_ratio_current_x96,
                    liquidity,
                    amount_remaining_less_fee,
                    zero_for_one
                )
        else:
            if zero_for_one:
                amount_out = SqrtPriceMath.get_amount1_delta(
                    sqrt_ratio_target_x96,
                    sqrt_ratio_current_x96,
                    liquidity,
                    False
                )
            else:
                amount_out = SqrtPriceMath.get_amount0_delta(
                    sqrt_ratio_current_x96,
                    sqrt_ratio_target_x96,
                    liquidity,
                    False
                )
            
            if -amount_remaining >= amount_out:
                sqrt_ratio_next_x96 = sqrt_ratio_target_x96
            else:
                sqrt_ratio_next_x96 = SqrtPriceMath.get_next_sqrt_price_from_output(
                    sqrt_ratio_current_x96,
                    liquidity,
                    -amount_remaining,
                    zero_for_one
                )
        
        max_price_reached = sqrt_ratio_target_x96 == sqrt_ratio_next_x96
        
        if zero_for_one:
            if not (max_price_reached and exact_in):
                amount_in = SqrtPriceMath.get_amount0_delta(
                    sqrt_ratio_next_x96,
                    sqrt_ratio_current_x96,
                    liquidity,
                    True
                )
            if not (max_price_reached and not exact_in):
                amount_out = SqrtPriceMath.get_amount1_delta(
                    sqrt_ratio_next_x96,
                    sqrt_ratio_current_x96,
                    liquidity,
                    False
                )
        else:
            if not (max_price_reached and exact_in):
                amount_in = SqrtPriceMath.get_amount1_delta(
                    sqrt_ratio_current_x96,
                    sqrt_ratio_next_x96,
                    liquidity,
                    True
                )
            if not (max_price_reached and not exact_in):
                amount_out = SqrtPriceMath.get_amount0_delta(
                    sqrt_ratio_current_x96,
                    sqrt_ratio_next_x96,
                    liquidity,
                    False
                )
        
        if not exact_in and amount_out > -amount_remaining:
            amount_out = -amount_remaining
        
        if exact_in and sqrt_ratio_next_x96 != sqrt_ratio_target_x96:
            fee_amount = amount_remaining - amount_in
        else:
            fee_amount = FullMath.mul_div_rounding_up(amount_in, fee_pips, 1000000 - fee_pips)
        
        return (sqrt_ratio_next_x96, amount_in, amount_out, fee_amount)


def sqrt_price_x96_to_price(sqrt_price_x96: int, decimals0: int, decimals1: int) -> float:
    """
    Convert sqrtPriceX96 to human-readable price
    
    Price = (sqrtPriceX96 / 2^96)^2 * (10^decimals0 / 10^decimals1)
    
    Args:
        sqrt_price_x96: Square root price in Q64.96 format
        decimals0: Decimals of token0
        decimals1: Decimals of token1
    
    Returns:
        Price as float (token1 per token0)
    """
    Q96 = 2 ** 96
    price = (sqrt_price_x96 / Q96) ** 2
    
    decimal_adjustment = 10 ** (decimals1 - decimals0)
    return price / decimal_adjustment


def price_to_sqrt_price_x96(price: float, decimals0: int, decimals1: int) -> int:
    """
    Convert human-readable price to sqrtPriceX96
    
    Args:
        price: Price (token1 per token0)
        decimals0: Decimals of token0
        decimals1: Decimals of token1
    
    Returns:
        Square root price in Q64.96 format
    """
    Q96 = 2 ** 96
    
    decimal_adjustment = 10 ** (decimals1 - decimals0)
    adjusted_price = price * decimal_adjustment
    
    sqrt_price = math.sqrt(adjusted_price)
    sqrt_price_x96 = int(sqrt_price * Q96)
    
    return sqrt_price_x96
