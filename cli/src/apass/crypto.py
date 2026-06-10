import json
import os
import struct
from dataclasses import dataclass

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


# Minimum viable payload size (version + salt + empty params + nonce + GCM tag).
_MIN_PAYLOAD_SIZE = 1 + SALT_LENGTH + KDF_PARAMS_LEN_SIZE + 2 + NONCE_LENGTH + 16

# Required keys in the KDF params JSON block.
_REQUIRED_KDF_KEYS = frozenset({"iterations", "memory_cost", "lanes"})

# Safety limits — reject payloads / plaintext that cannot be legitimate.
_MAX_PAYLOAD_BYTES = 100 * 1024 * 1024   # 100 MiB
_MAX_PLAINTEXT_BYTES = 10 * 1024 * 1024  # 10 MiB


class VaultStructureError(Exception):
    """Payload envelope is structurally invalid — the file itself is the problem.

    Raised *before* any expensive key derivation (Argon2).  Callers can use
    this to tell the user that the vault file is corrupted, not the password.
    """


class DecryptionError(Exception):
    """GCM authentication failed — most likely the password is wrong.

    Raised *after* key derivation, so an attacker cannot obtain this signal
    without paying the Argon2 cost.
    """


@dataclass
class _Envelope:
    salt: bytes
    kdf_params: dict[str, int]
    nonce: bytes
    ciphertext: bytes


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
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

    return (
        bytes([PAYLOAD_VERSION])
        + salt
        + struct.pack(">H", len(kdf_params_json))
        + kdf_params_json
        + nonce
        + ciphertext
    )


def decrypt(payload: bytes, password: str) -> bytes:
    """Decrypt *payload* previously produced by :func:`encrypt`.

    Returns the original plaintext.

    :raises VaultStructureError: the payload envelope is malformed
        (corrupted file, unsupported version, unreasonable size).
    :raises DecryptionError: password is wrong or the ciphertext has been
        tampered with.
    """
    envelope = _parse_envelope(payload)
    key = _derive_key(
        password,
        envelope.salt,
        envelope.kdf_params["iterations"],
        envelope.kdf_params["memory_cost"],
        envelope.kdf_params["lanes"],
    )
    try:
        plaintext = AESGCM(key).decrypt(
            envelope.nonce, envelope.ciphertext, None
        )
    except InvalidTag:
        raise DecryptionError() from None

    if len(plaintext) > _MAX_PLAINTEXT_BYTES:
        raise VaultStructureError("Plaintext exceeds maximum size")

    return plaintext


def _parse_envelope(payload: bytes) -> _Envelope:
    """Parse and validate the payload envelope in a single pass.

    Returns the extracted components without deriving any keys.

    :raises VaultStructureError: on any structural problem.
    """
    if len(payload) < _MIN_PAYLOAD_SIZE:
        raise VaultStructureError("Payload too short")
    if len(payload) > _MAX_PAYLOAD_BYTES:
        raise VaultStructureError("Payload exceeds maximum size")

    pos = 0

    version = payload[pos]
    pos += 1
    if version != PAYLOAD_VERSION:
        raise VaultStructureError(
            f"Unsupported payload version {version}, expected {PAYLOAD_VERSION}"
        )

    salt = payload[pos : pos + SALT_LENGTH]
    pos += SALT_LENGTH

    kdf_params_len = struct.unpack(
        ">H", payload[pos : pos + KDF_PARAMS_LEN_SIZE]
    )[0]
    pos += KDF_PARAMS_LEN_SIZE

    if len(payload) < pos + kdf_params_len + NONCE_LENGTH + 16:
        raise VaultStructureError(
            "Payload too short for declared KDF params + nonce + GCM tag"
        )

    kdf_params_json = payload[pos : pos + kdf_params_len]
    pos += kdf_params_len

    try:
        kdf_params = json.loads(kdf_params_json)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise VaultStructureError("KDF params are not valid JSON") from None

    if not _REQUIRED_KDF_KEYS.issubset(kdf_params.keys()):
        missing = _REQUIRED_KDF_KEYS - kdf_params.keys()
        raise VaultStructureError(
            f"KDF params missing required keys: {sorted(missing)}"
        )

    nonce = payload[pos : pos + NONCE_LENGTH]
    pos += NONCE_LENGTH

    ciphertext = payload[pos:]

    return _Envelope(salt, kdf_params, nonce, ciphertext)


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



