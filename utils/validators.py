"""
Wallet address validation utilities for Gemlaunch.fun

This module provides reusable validation functions for various wallet address formats,
including EVM-compatible wallets (Ethereum, etc.) and Kaspa wallets.
"""

import re
from typing import Optional

# Compiled regex patterns for performance
_EVM_ADDRESS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')
_KASPA_ADDRESS_PATTERN = re.compile(r'^kaspa:[a-z0-9]{61,63}$')


def validate_eth_wallet_address(address: str) -> str:
    """
    Validate and normalize EVM wallet address format.
    
    This function validates Ethereum and other EVM-compatible wallet addresses,
    ensuring they match the standard format of '0x' followed by 40 hexadecimal
    characters. The validation is case-insensitive for the hex portion.
    
    Args:
        address (str): The wallet address to validate. Should be in format
                      '0x' + 40 hexadecimal characters (case-insensitive).
    
    Returns:
        str: The validated wallet address in lowercase format.
             Example: '0xa51d8f597570353ae50a25df90ade162d2305ffa'
    
    Raises:
        ValueError: If the address is None, empty, not a string, or doesn't
                   match the required EVM address format.
    
    Examples:
        >>> validate_eth_wallet_address('0xA51D8F597570353AE50A25DF90ADE162D2305FFA')
        '0xa51d8f597570353ae50a25df90ade162d2305ffa'
        
        >>> validate_eth_wallet_address('0x1234')
        ValueError: Invalid wallet address format. Must be 0x followed by 40 hexadecimal characters.
        
        >>> validate_eth_wallet_address('not_a_wallet')
        ValueError: Invalid wallet address format. Must be 0x followed by 40 hexadecimal characters.
    
    Note:
        - The function uses a compiled regex pattern for optimal performance
        - All valid addresses are returned in lowercase for consistency
        - This validator is suitable for Ethereum, Polygon, BSC, and other EVM chains
    """
    if not address:
        raise ValueError('Wallet address is required and cannot be empty.')
    
    if not isinstance(address, str):
        raise ValueError('Wallet address must be a string.')
    
    # Strip whitespace
    address = address.strip()
    
    # Validate format using compiled regex
    if not _EVM_ADDRESS_PATTERN.match(address):
        raise ValueError(
            'Invalid wallet address format. '
            'Must be 0x followed by 40 hexadecimal characters.'
        )
    
    # Return normalized (lowercase) address
    return address.lower()


def validate_kaspa_address(address: str) -> str:
    """
    Validate and normalize Kaspa wallet address format.
    
    This function validates Kaspa wallet addresses, ensuring they match the
    standard Kaspa address format. Note: Full Kaspa address validation may
    require additional checksum verification not implemented here.
    
    Args:
        address (str): The Kaspa wallet address to validate. Should start with
                      'kaspa:' followed by 61-63 lowercase alphanumeric characters.
    
    Returns:
        str: The validated Kaspa wallet address in lowercase format.
             Example: 'kaspa:qp...'
    
    Raises:
        ValueError: If the address is None, empty, not a string, or doesn't
                   match the basic Kaspa address format.
    
    Examples:
        >>> validate_kaspa_address('kaspa:qp0123456789abcdef...')
        'kaspa:qp0123456789abcdef...'
        
        >>> validate_kaspa_address('invalid_kaspa')
        ValueError: Invalid Kaspa address format. Must start with 'kaspa:' followed by alphanumeric characters.
    
    Note:
        - This is a basic format validator
        - Production systems should implement full Kaspa checksum validation
        - The function uses a compiled regex pattern for optimal performance
    """
    if not address:
        raise ValueError('Kaspa address is required and cannot be empty.')
    
    if not isinstance(address, str):
        raise ValueError('Kaspa address must be a string.')
    
    # Strip whitespace and convert to lowercase
    address = address.strip().lower()
    
    # Validate format using compiled regex (basic check)
    if not _KASPA_ADDRESS_PATTERN.match(address):
        raise ValueError(
            'Invalid Kaspa address format. '
            'Must start with \'kaspa:\' followed by alphanumeric characters.'
        )
    
    # Return normalized address
    return address


def is_valid_eth_address(address: Optional[str]) -> bool:
    """
    Check if a string is a valid EVM wallet address without raising exceptions.
    
    This is a convenience function that wraps validate_eth_wallet_address()
    and returns a boolean instead of raising exceptions. Useful for conditional
    checks where you don't want to handle exceptions.
    
    Args:
        address (Optional[str]): The wallet address to check.
    
    Returns:
        bool: True if the address is valid, False otherwise.
    
    Examples:
        >>> is_valid_eth_address('0xA51D8F597570353AE50A25DF90ADE162D2305FFA')
        True
        
        >>> is_valid_eth_address('invalid')
        False
        
        >>> is_valid_eth_address(None)
        False
    """
    try:
        validate_eth_wallet_address(address)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def is_valid_kaspa_address(address: Optional[str]) -> bool:
    """
    Check if a string is a valid Kaspa wallet address without raising exceptions.
    
    This is a convenience function that wraps validate_kaspa_address()
    and returns a boolean instead of raising exceptions.
    
    Args:
        address (Optional[str]): The Kaspa wallet address to check.
    
    Returns:
        bool: True if the address is valid, False otherwise.
    
    Examples:
        >>> is_valid_kaspa_address('kaspa:qp0123...')
        True
        
        >>> is_valid_kaspa_address('invalid')
        False
    """
    try:
        validate_kaspa_address(address)
        return True
    except (ValueError, TypeError, AttributeError):
        return False
