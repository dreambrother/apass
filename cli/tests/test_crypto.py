"""Integration tests for the crypto module — own encrypt/decrypt round-trip."""

import pytest

from apass.crypto import (
    AAD,
    PAYLOAD_VERSION,
    decrypt,
    encrypt,
)


def test_round_trip() -> None:
    plaintext = b"hello, world!"
    password = "correct-horse-battery-staple"
    ciphertext = encrypt(plaintext, password)
    assert decrypt(ciphertext, password) == plaintext


def test_wrong_password_returns_none() -> None:
    ciphertext = encrypt(b"secret", "right-password")
    assert decrypt(ciphertext, "wrong-password") is None


def test_tampered_ciphertext_returns_none() -> None:
    ciphertext = encrypt(b"secret", "password")
    mutated = bytearray(ciphertext)
    # Flip a bit deep inside the ciphertext region (after version, salt, params, nonce).
    mutated[-3] ^= 0x01
    assert decrypt(bytes(mutated), "password") is None


def test_short_payload_returns_none() -> None:
    assert decrypt(b"short", "password") is None


def test_version_byte_is_present() -> None:
    ciphertext = encrypt(b"data", "pass")
    assert ciphertext[0] == PAYLOAD_VERSION


def test_aad_is_bound() -> None:
    """If the AAD constant changes, existing ciphertexts must fail."""
    ciphertext = encrypt(b"data", "pass")

    import apass.crypto as crypto_module
    original_aad = crypto_module.AAD
    try:
        # Simulate a future version with a different AAD.
        crypto_module.AAD = b"apass-v2"
        assert decrypt(ciphertext, "pass") is None
    finally:
        crypto_module.AAD = original_aad
