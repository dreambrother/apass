"""Integration tests for the crypto module — encrypt/decrypt round-trip."""

import pytest

from apass.crypto import (
    AAD,
    PAYLOAD_VERSION,
    DecryptionError,
    VaultStructureError,
    decrypt,
    encrypt,
)


@pytest.fixture(autouse=True)
def fast_argon2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests by using minimal Argon2 parameters.

    Parameters are stored inside the payload, so round-trip still works.
    """
    import apass.crypto as c

    monkeypatch.setattr(c, "DEFAULT_ARGON2_MEMORY", 8)
    monkeypatch.setattr(c, "DEFAULT_ARGON2_ITERATIONS", 1)
    monkeypatch.setattr(c, "DEFAULT_ARGON2_LANES", 1)


def test_round_trip() -> None:
    plaintext = b"hello, world!"
    password = "correct-horse-battery-staple"
    ciphertext = encrypt(plaintext, password)
    assert decrypt(ciphertext, password) == plaintext


def test_wrong_password_raises_decryption_error() -> None:
    ciphertext = encrypt(b"secret", "right-password")
    with pytest.raises(DecryptionError):
        decrypt(ciphertext, "wrong-password")


def test_tampered_ciphertext_raises_decryption_error() -> None:
    ciphertext = encrypt(b"secret", "password")
    mutated = bytearray(ciphertext)
    mutated[-3] ^= 0x01
    with pytest.raises(DecryptionError):
        decrypt(bytes(mutated), "password")


def test_short_payload_raises_structure_error() -> None:
    with pytest.raises(VaultStructureError, match="Payload too short"):
        decrypt(b"short", "password")


def test_wrong_version_raises_structure_error() -> None:
    ciphertext = encrypt(b"data", "pass")
    mutated = bytearray(ciphertext)
    mutated[0] = 99  # unsupported version
    with pytest.raises(VaultStructureError, match="Unsupported payload version"):
        decrypt(bytes(mutated), "pass")


def test_bad_kdf_json_raises_structure_error() -> None:
    ciphertext = encrypt(b"data", "pass")
    mutated = bytearray(ciphertext)
    pos = 1 + 16  # version + salt
    mutated[pos] = 0xFF
    mutated[pos + 1] = 0xFF
    with pytest.raises(VaultStructureError):
        decrypt(bytes(mutated), "pass")


def test_version_byte_is_present() -> None:
    ciphertext = encrypt(b"data", "pass")
    assert ciphertext[0] == PAYLOAD_VERSION


def test_aad_is_bound() -> None:
    """If the AAD constant changes, existing ciphertexts must fail."""
    ciphertext = encrypt(b"data", "pass")

    import apass.crypto as crypto_module
    original_aad = crypto_module.AAD
    try:
        crypto_module.AAD = b"apass-v2"
        with pytest.raises(DecryptionError):
            decrypt(ciphertext, "pass")
    finally:
        crypto_module.AAD = original_aad
