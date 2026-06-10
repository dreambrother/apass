<p align="center"><img src="assets/logo.png" alt="APass logo" width="400"></p>

# APass

A dead-simple cross-platform **A**nother **Pass**word manager.

## Status

**Under active development.** CLI is functional — generates a password, copies it to the clipboard, and persists it in an encrypted local vault.

## CLI Features

- [x] Init (create the local vault)
- [x] Create
- [x] Get
- [x] Save
- [ ] Remove
- [ ] Rotate
- [x] Cloud sync (Google Drive, Yandex Disk)
- [x] Delete remote vault file

## CLI

Install and run:

```bash
cd cli
poetry install
poetry run apass init
poetry run apass create github
```

Requires **Python ≥ 3.14**, Poetry 2.x.

### Commands

#### `apass init`

Create a new encrypted vault. Prompts for a master password (min 8 characters, 12+ recommended).

```bash
poetry run apass init
```

#### `apass create <name>`

Generate a new password, copy it to the clipboard, and store it in the vault.

```bash
poetry run apass create github
poetry run apass create github --size 24 --min-digits 2 --min-special 2
```

| Option | Short | Description | Default |
|---|---|---|---|
| `--size` | `-s` | Password length | 18 |
| `--min-digits` | `-d` | Minimum number of digits (0 to disable) | — |
| `--min-special` | `-p` | Minimum number of special characters (0 to disable) | — |
| `--login` | `-l` | Service/utility login | — |

#### `apass get <name>`

Search for a password by name and copy it to the clipboard. If multiple entries match, prompts to choose one.

```bash
poetry run apass get github
```

#### `apass save <name>`

Save an existing password to the vault.

```bash
poetry run apass save github
poetry run apass save github --force
```

| Option | Short | Description | Default |
|---|---|---|---|
| `--force` | `-f` | Overwrite existing entry | `false` |
| `--login` | `-l` | Service/utility login | — |

### Sync

Sync your vault across devices via Google Drive or Yandex Disk.

#### Setup

**Google Drive:**

1. **Register a Google Cloud project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or use existing)
   - Enable **Google Drive API**
   - Go to **APIs & Services → OAuth consent screen** → **Add or remove scopes**
   - Add the following scopes:
     - `https://www.googleapis.com/auth/drive.appdata`
     - `https://www.googleapis.com/auth/userinfo.email`
   - Go to **Credentials** → **Create Credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Under **Authorized redirect URIs**, add: `http://127.0.0.1`
   - Click **Create** and note the **Client ID** and **Client Secret**

2. **Configure apass:**
   ```bash
   poetry run apass sync setup
   # Enter client_id and client_secret when prompted
   ```

**Yandex Disk:**

1. **Register a Yandex OAuth application:**
   - Go to [Yandex OAuth](https://oauth.yandex.ru/client/new)
   - Fill in the application name (e.g., `APass`)
   - Enable **Web services** platform
   - Under **Redirect URI**, add: `http://127.0.0.1:9000`
   - Under **Yandex.Disk API**, select scopes: `cloud_api:disk.read`, `cloud_api:disk.write`
   - Click **Create** and note the **Client ID** and **Client Secret**

2. **Configure apass:**
   ```bash
   poetry run apass sync setup --backend yadisk
   # Enter client_id and client_secret when prompted
   ```

**Login:**
```bash
poetry run apass sync login
# Browser opens for OAuth consent
```

#### Commands

| Command | Description |
|---|---|
| `apass sync setup [-b gdrive\|yadisk]` | Configure OAuth credentials (one-time) |
| `apass sync login` | Authorize apass to access cloud storage |
| `apass sync logout` | Remove authorization |
| `apass sync status` | Show sync status (backend, email, file ID, last sync time) |
| `apass sync diff` | Preview what would be synced (dry run) |
| `apass sync push` | Merge local + remote, upload to cloud |
| `apass sync pull` | Merge remote + local, download from cloud |
| `apass sync delete-remote [--yes]` | Permanently delete the remote vault file from cloud storage |
| `apass sync backend gdrive\|yadisk` | Switch cloud storage backend |

#### Storage details

- **Google Drive:** vault stored in hidden app data folder — only apass can access it
- **Yandex Disk:** vault stored at `/apass/vault.db` — visible in web interface

#### Merge strategy

- Entries are merged by `name` (case-sensitive)
- Conflicts resolved by last-write-wins using `modified` timestamp
- On equal timestamps: `push` prefers local, `pull` prefers remote
- No interactive conflict resolution in v1

### Environment variables

| Variable | Description |
|---|---|
| `APASS_DB_PATH` | Path to the vault file (default: `~/.apass/vault.db`) |

## Android

TODO. Mobile client development begins after CLI and vault format stabilize.

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
