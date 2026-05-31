import json
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

SALT_LENGTH = 16
NONCE_LENGTH = 12
KEY_LENGTH = 32
KDF_PARAMS_LEN_SIZE = 2  # uint16 big-endian

# Current format version.  Written as a single byte prefix.
# Increment when the payload layout changes in a backward-incompatible way.
PAYLOAD_VERSION: int = 1

# Default KDF parameters used when creating new vaults.
# Encryption writes these into the payload, so old vaults are not affected
# when defaults change — decryption reads params from the ciphertext.
DEFAULT_ARGON2_ITERATIONS = 4
DEFAULT_ARGON2_MEMORY = 131072  # 128 MiB
DEFAULT_ARGON2_LANES = 4

# Associated data bound to every AES-GCM operation to prevent
# ciphertext substitution across different contexts.
AAD = b"apass-v1"

# Minimum viable payload size (version + salt + empty params + nonce + GCM tag).
_MIN_PAYLOAD_SIZE = 1 + SALT_LENGTH + KDF_PARAMS_LEN_SIZE + 2 + NONCE_LENGTH + 16


def encrypt(plaintext: bytes, password: str) -> bytes:
    """Encrypt *plaintext* under *password* using AES-256-GCM.

    Returns a self-describing byte string:

        version(1) | salt(16) | kdf_params_len(2, big-endian) |
        kdf_params_json | nonce(12) | ciphertext+tag
    """
    salt = os.urandom(SALT_LENGTH)
    kdf_params = {
        "iterations": DEFAULT_ARGON2_ITERATIONS,
        "memory_cost": DEFAULT_ARGON2_MEMORY,
        "lanes": DEFAULT_ARGON2_LANES,
    }
    kdf_params_json = json.dumps(kdf_params, separators=(",", ":")).encode("utf-8")
    if len(kdf_params_json) > 65535:
        raise ValueError("KDF params too large")

    key = _derive_key(
        password,
        salt,
        kdf_params["iterations"],
        kdf_params["memory_cost"],
        kdf_params["lanes"],
    )
    nonce = os.urandom(NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)

    return (
        bytes([PAYLOAD_VERSION])
        + salt
        + struct.pack(">H", len(kdf_params_json))
        + kdf_params_json
        + nonce
        + ciphertext
    )


def decrypt(payload: bytes, password: str) -> bytes | None:
    """Decrypt *payload* previously produced by :func:`encrypt`.

    Returns the original plaintext, or ``None`` when the password is wrong
    or the payload has been tampered with (GCM authentication failure).
    """
    if len(payload) < _MIN_PAYLOAD_SIZE:
        return None

    pos = 0

    version = payload[pos]
    pos += 1
    if version != PAYLOAD_VERSION:
        return None

    salt = payload[pos : pos + SALT_LENGTH]
    pos += SALT_LENGTH

    kdf_params_len = struct.unpack(">H", payload[pos : pos + KDF_PARAMS_LEN_SIZE])[0]
    pos += KDF_PARAMS_LEN_SIZE

    if len(payload) < pos + kdf_params_len + NONCE_LENGTH + 16:
        return None

    kdf_params_json = payload[pos : pos + kdf_params_len]
    pos += kdf_params_len

    try:
        kdf_params = json.loads(kdf_params_json)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    nonce = payload[pos : pos + NONCE_LENGTH]
    pos += NONCE_LENGTH

    ciphertext = payload[pos:]

    key = _derive_key(
        password,
        salt,
        kdf_params.get("iterations", DEFAULT_ARGON2_ITERATIONS),
        kdf_params.get("memory_cost", DEFAULT_ARGON2_MEMORY),
        kdf_params.get("lanes", DEFAULT_ARGON2_LANES),
    )
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except InvalidTag:
        return None


def _derive_key(
    password: str,
    salt: bytes,
    iterations: int,
    memory_cost: int,
    lanes: int,
) -> bytes:
    kdf = Argon2id(
        salt=salt,
        length=KEY_LENGTH,
        iterations=iterations,
        memory_cost=memory_cost,
        lanes=lanes,
    )
    return kdf.derive(password.encode("utf-8"))
