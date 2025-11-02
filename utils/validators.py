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


def validate_positive_integer(value: any, field_name: str = "Value", min_value: int = 1, max_value: Optional[int] = None) -> int:
    """
    Validate that a value is a positive integer within optional bounds.
    
    Args:
        value: The value to validate (can be int, str, or float)
        field_name: Name of the field for error messages
        min_value: Minimum allowed value (default: 1)
        max_value: Maximum allowed value (optional)
    
    Returns:
        int: The validated integer value
    
    Raises:
        ValueError: If value is not a valid positive integer or out of bounds
    
    Examples:
        >>> validate_positive_integer("100", "Token Amount")
        100
        
        >>> validate_positive_integer(-5, "Amount")
        ValueError: Amount must be a positive integer
    """
    try:
        # Convert to int
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid integer")
    
    # Check if positive
    if int_value < min_value:
        raise ValueError(f"{field_name} must be at least {min_value}")
    
    # Check max bound if provided
    if max_value is not None and int_value > max_value:
        raise ValueError(f"{field_name} must not exceed {max_value}")
    
    return int_value


def validate_percentage(value: any, field_name: str = "Percentage") -> float:
    """
    Validate that a value is a valid percentage between 0 and 100.
    
    Args:
        value: The percentage to validate (can be int, str, or float)
        field_name: Name of the field for error messages
    
    Returns:
        float: The validated percentage value
    
    Raises:
        ValueError: If value is not a valid percentage or out of range [0, 100]
    
    Examples:
        >>> validate_percentage("50.5")
        50.5
        
        >>> validate_percentage(150)
        ValueError: Percentage must be between 0 and 100
    """
    try:
        # Convert to float
        float_value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid number")
    
    # Check range [0, 100]
    if float_value < 0 or float_value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    
    return float_value


def sanitize_text_input(text: str, max_length: Optional[int] = None, field_name: str = "Text") -> str:
    """
    Sanitize user text input to prevent XSS attacks.
    
    This function:
    1. Strips leading/trailing whitespace
    2. Removes dangerous HTML/script tags
    3. Limits length if specified
    4. Preserves safe formatting (newlines, basic punctuation)
    
    Args:
        text: The text to sanitize
        max_length: Maximum allowed length (optional)
        field_name: Name of the field for error messages
    
    Returns:
        str: The sanitized text
    
    Raises:
        ValueError: If text is empty after sanitization or exceeds max_length
    
    Examples:
        >>> sanitize_text_input("Hello <script>alert('xss')</script>")
        "Hello alert('xss')"
        
        >>> sanitize_text_input("Normal text")
        "Normal text"
    """
    if not text or not isinstance(text, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    
    # Strip whitespace
    text = text.strip()
    
    if not text:
        raise ValueError(f"{field_name} cannot be empty or whitespace only")
    
    # Remove dangerous HTML tags (basic XSS prevention)
    # Remove script tags and their content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove style tags and their content
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove iframe tags
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove event handlers (onclick, onerror, etc.)
    text = re.sub(r'\s*on\w+\s*=\s*["\']?[^"\']*["\']?', '', text, flags=re.IGNORECASE)
    
    # Remove javascript: protocol
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Check max length
    if max_length and len(text) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    
    return text
