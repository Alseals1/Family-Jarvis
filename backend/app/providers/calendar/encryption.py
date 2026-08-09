"""
Symmetric encryption for OAuth refresh tokens at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
The key is sourced from CALENDAR_ENCRYPTION_KEY in the environment — a
64-character hex string (32 bytes of entropy). It is never logged.

Usage:
    ciphertext = encrypt_token(plaintext, settings.CALENDAR_ENCRYPTION_KEY)
    plaintext  = decrypt_token(ciphertext, settings.CALENDAR_ENCRYPTION_KEY)
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken


def _make_fernet(key: str) -> Fernet:
    """
    Convert a 64-char hex key to a Fernet instance.

    Fernet requires a 32-byte key that is base64url-encoded (44 chars with
    trailing '='). We store the raw key as hex for readability/generation
    convenience and convert here.
    """
    key_bytes = bytes.fromhex(key)          # 64 hex chars → 32 bytes
    fernet_key = base64.urlsafe_b64encode(key_bytes)   # 32 bytes → 44-char b64
    return Fernet(fernet_key)


def encrypt_token(plaintext: str, key: str) -> str:
    """
    Encrypt a plaintext OAuth token using Fernet symmetric encryption.

    Args:
        plaintext: The raw token string to encrypt.
        key:       64-character hex string (CALENDAR_ENCRYPTION_KEY).

    Returns:
        Base64-encoded ciphertext as a plain string, safe for TEXT column
        storage.
    """
    f = _make_fernet(key)
    ciphertext_bytes = f.encrypt(plaintext.encode("utf-8"))
    return ciphertext_bytes.decode("utf-8")


def decrypt_token(ciphertext: str, key: str) -> str:
    """
    Decrypt a Fernet ciphertext back to a plaintext OAuth token.

    Args:
        ciphertext: Base64-encoded ciphertext produced by encrypt_token.
        key:        64-character hex string (CALENDAR_ENCRYPTION_KEY).

    Returns:
        Original plaintext string.

    Raises:
        ValueError: If the key is invalid, the ciphertext is corrupted, or
                    the token was encrypted with a different key.
    """
    try:
        f = _make_fernet(key)
        plaintext_bytes = f.decrypt(ciphertext.encode("utf-8"))
        return plaintext_bytes.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Token decryption failed: invalid key or corrupted ciphertext"
        ) from exc
    except (ValueError, Exception) as exc:
        raise ValueError(
            f"Token decryption failed: {exc}"
        ) from exc


def is_valid_key(key: str) -> bool:
    """
    Return True iff key is a valid 64-character hex string (32 bytes).

    Used in application startup health checks.
    """
    if not isinstance(key, str):
        return False
    if len(key) != 64:
        return False
    try:
        bytes.fromhex(key)
        return True
    except ValueError:
        return False
