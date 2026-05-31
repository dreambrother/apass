import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

SALT_LENGTH = 16
NONCE_LENGTH = 12
KEY_LENGTH = 32
ARGON2_ITERATIONS = 3
ARGON2_MEMORY = 65536
ARGON2_LANES = 4


def encrypt(plaintext: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_LENGTH)
    key = _derive_key(password, salt)
    nonce = os.urandom(NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return salt + nonce + ciphertext


def decrypt(payload: bytes, password: str) -> bytes | None:
    salt = payload[:SALT_LENGTH]
    nonce = payload[SALT_LENGTH:SALT_LENGTH + NONCE_LENGTH]
    if len(payload) <= SALT_LENGTH + NONCE_LENGTH:
        return None
    ciphertext = payload[SALT_LENGTH + NONCE_LENGTH:]
    key = _derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        return None


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Argon2id(
        salt=salt,
        length=KEY_LENGTH,
        iterations=ARGON2_ITERATIONS,
        memory_cost=ARGON2_MEMORY,
        lanes=ARGON2_LANES,
    )
    return kdf.derive(password.encode("utf-8"))
