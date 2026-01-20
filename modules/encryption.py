"""
Encryption/Decryption utilities for secure data handling
"""

from cryptography.fernet import Fernet
import streamlit as st
import io
from typing import BinaryIO

def get_encryption_key() -> bytes:
    """
    Get encryption key from Streamlit secrets.

    Returns:
        Encryption key as bytes

    Raises:
        ValueError: If key is not configured
    """
    try:
        # Try to get key from Streamlit secrets
        key = st.secrets.get("EXCEL_ENCRYPTION_KEY")
        if key:
            return key.encode() if isinstance(key, str) else key
    except (AttributeError, FileNotFoundError):
        pass

    # Fallback for local development without encryption
    # In production, this will raise an error if key is not set
    raise ValueError(
        "Encryption key not found. "
        "Please add EXCEL_ENCRYPTION_KEY to Streamlit secrets."
    )

def decrypt_file(encrypted_data: bytes) -> bytes:
    """
    Decrypt encrypted file data.

    Args:
        encrypted_data: Encrypted file contents

    Returns:
        Decrypted file contents as bytes
    """
    key = get_encryption_key()
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_data)

def decrypt_file_to_stream(encrypted_file_path: str) -> BinaryIO:
    """
    Decrypt an encrypted file and return as a file-like object (in memory).

    Args:
        encrypted_file_path: Path to encrypted file

    Returns:
        BytesIO object containing decrypted data
    """
    # Read encrypted file
    with open(encrypted_file_path, 'rb') as f:
        encrypted_data = f.read()

    # Decrypt
    decrypted_data = decrypt_file(encrypted_data)

    # Return as file-like object
    return io.BytesIO(decrypted_data)

def is_encrypted_file(file_path: str) -> bool:
    """
    Check if a file appears to be encrypted (by extension or content).

    Args:
        file_path: Path to check

    Returns:
        True if file appears encrypted
    """
    return file_path.endswith('.encrypted') or file_path.endswith('.enc')
