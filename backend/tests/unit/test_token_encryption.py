"""
Unit tests for app.providers.calendar.encryption — OAuth token encryption.
"""

import pytest
import secrets

from app.providers.calendar.encryption import (
    decrypt_token,
    encrypt_token,
    is_valid_key,
)

# A valid 64-char hex key (32 bytes of entropy)
VALID_KEY = secrets.token_hex(32)  # 64 hex chars
VALID_KEY_2 = secrets.token_hex(32)  # Different valid key


def test_encrypt_decrypt_roundtrip():
    """encrypt then decrypt returns the original string."""
    plaintext = "ya29.some-real-looking-access-token"
    ciphertext = encrypt_token(plaintext, VALID_KEY)
    result = decrypt_token(ciphertext, VALID_KEY)
    assert result == plaintext


def test_different_plaintext_different_ciphertext():
    """Same key, different inputs → different ciphertexts (Fernet adds IV)."""
    ct1 = encrypt_token("token-aaa", VALID_KEY)
    ct2 = encrypt_token("token-bbb", VALID_KEY)
    assert ct1 != ct2


def test_wrong_key_raises_error():
    """Decrypting with the wrong key raises ValueError."""
    ciphertext = encrypt_token("secret-refresh-token", VALID_KEY)
    with pytest.raises(ValueError):
        decrypt_token(ciphertext, VALID_KEY_2)


def test_corrupted_ciphertext_raises_error():
    """Tampered ciphertext raises ValueError."""
    ciphertext = encrypt_token("secret-refresh-token", VALID_KEY)
    # Corrupt the middle of the ciphertext
    corrupted = ciphertext[:10] + "XXXXXX" + ciphertext[16:]
    with pytest.raises(ValueError):
        decrypt_token(corrupted, VALID_KEY)


def test_valid_key_check():
    """is_valid_key returns True for 64-char hex, False otherwise."""
    assert is_valid_key(VALID_KEY) is True
    # 32-char hex (16 bytes) — too short
    assert is_valid_key(secrets.token_hex(16)) is False
    # Non-hex characters
    assert is_valid_key("z" * 64) is False
    # Empty string
    assert is_valid_key("") is False
    # None
    assert is_valid_key(None) is False  # type: ignore[arg-type]


def test_empty_string_encrypts_correctly():
    """Edge case: empty string roundtrips cleanly."""
    plaintext = ""
    ciphertext = encrypt_token(plaintext, VALID_KEY)
    result = decrypt_token(ciphertext, VALID_KEY)
    assert result == plaintext
