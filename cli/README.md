# apass

CLI password manager.

## Encryption

The vault file is encrypted using **Argon2id + AES-256-GCM**.

### How it works

1. **Key derivation** — 32-byte salt + master password → Argon2id → 256-bit key.
2. **Encryption** — plaintext (JSON-serialized vault) is encrypted with AES-256-GCM using a random 12-byte nonce.
3. **File format** — `salt(16) || nonce(12) || ciphertext + tag`.

Argon2id parameters: `iterations=3`, `memory_cost=65536` (64 MB), `lanes=4`.

### Brute-force resistance

The bottleneck is Argon2id, not AES. Even with unlimited GPU/ASIC hardware, each password guess requires 64 MB of RAM and 3 passes over it. This makes brute-force attacks orders of magnitude slower than PBKDF2.

| Password strength | Entropy | Time to crack (8× RTX 4090) |
|---|---|---|
| `qwerty12` (weak) | ~41 bit | ~17 years |
| 4 random words | ~52 bit | ~35 000 years |
| 6 Diceware words | ~77 bit | ~10¹² years |

For comparison, the same passwords with PBKDF2-SHA256 (600k iterations) would fall in days to months.

### Wrong password detection

GCM authentication tag ensures that any wrong password or file corruption is detected immediately — decryption returns `None` instead of garbage data.
