<p align="center"><img src="assets/logo.png" alt="APass logo" width="400"></p>

# APass

A dead-simple cross-platform **A**nother **Pass**word manager.

## Status

**Under development.** CLI is functional, Android app is planned.

## CLI Features

- [x] Init (create the local vault)
- [x] Create
- [x] Get
- [x] Save
- [x] List
- [x] Remove (moves entry to Recycle Bin)
- [x] Restore (recover entry from Recycle Bin)
- [x] Cloud sync (Google Drive, Yandex Disk)
- [x] Delete remote vault file
- [x] Multiline note
- [ ] Don't ask for password every run
- [ ] List Recycle Bin
- [ ] Rotate
- [ ] Remove from bin
- [ ] Rename entry

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
| `--note` | `-n` | Note text | — |
| `--note-edit` | `-E` | Open `$EDITOR` for multiline note | — |

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
| `--note` | `-n` | Note text | — |
| `--note-edit` | `-E` | Open `$EDITOR` for multiline note | — |

#### `apass remove <name>`

Move an entry to the Recycle Bin. It can be recovered with `apass restore`.

```bash
poetry run apass remove github
```

#### `apass restore <name>`

Restore an entry from the Recycle Bin. Searches trashed entries by name (substring, case-insensitive). If multiple match, prompts to choose one.

```bash
poetry run apass restore github
```

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
| `apass sync run` | Bidirectional sync: merge local + remote, write to both |
| `apass sync delete-remote [--yes]` | Permanently delete the remote vault file from cloud storage |
| `apass sync backend gdrive\|yadisk` | Switch cloud storage backend |

#### Storage details

- **Google Drive:** vault stored in hidden app data folder — only apass can access it
- **Yandex Disk:** vault stored at `/apass/vault.kdbx` — visible in web interface

#### Merge strategy

- Entries are merged by `uuid` (standard KDBX entry identifier)
- Conflicts resolved by last-write-wins using the entry's modification time
- On equal timestamps: local wins
- Deletions are stored in the KDBX Recycle Bin; the merge also propagates them with LWW
- No interactive conflict resolution in v1

### Environment variables

| Variable | Description |
|---|---|
| `APASS_DB_PATH` | Path to the vault file (default: `~/.apass/vault.kdbx`) |

## Android

Mobile clients (KeePassDX, KeePass2Android, KeePassXC) can open the same vault file directly.

## Encryption & compatibility

The vault file uses the **KDBX 4** format (KeePass 2.x) and is compatible with:

- KeePassXC (Linux, macOS, Windows)
- KeePassDX and KeePass2Android (Android)
- Strongbox (iOS / macOS)
- KeeWeb (web)
- Any other KeePass-compatible client

Under the hood:

1. **Key derivation** — master password → Argon2id (KDBX 4 default) → 256-bit key.
2. **Encryption** — XML payload is encrypted with AES-256-CBC + HMAC-SHA256 (KDBX 4 defaults).
3. **File format** — KDBX 4 envelope as specified by the [KeePass file format docs](https://keepass.info/help/kb/kdbx.html).

The Recycle Bin is the standard KDBX "Recycle Bin" group; entries in it are considered deleted by apass and excluded from search/get.

### Brute-force resistance

The bottleneck is Argon2id, not AES. With KDBX 4 defaults, each password guess requires significant RAM and CPU. This makes brute-force attacks orders of magnitude slower than PBKDF2.

| Password strength | Entropy | Time to crack (8× RTX 4090) |
|---|---|---|
| `qwerty12` (weak) | ~41 bit | years |
| 4 random words | ~52 bit | thousands of years |
| 6 Diceware words | ~77 bit | ~10¹² years |

For comparison, the same passwords with PBKDF2-SHA256 (600k iterations) would fall in days to months.

### Wrong password detection

KDBX authentication (HMAC-SHA256) ensures that any wrong password or file corruption is detected immediately — the vault reports `Wrong password or corrupted vault`.
