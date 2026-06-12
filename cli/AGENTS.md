# AGENTS.md — apass

```

## Setup

```bash
poetry install
```

## Run tests

```bash
poetry run pytest
```

To run a single test:

```bash
poetry run pytest tests/test_cli.py::test_create_prompts_for_password_and_stores
```

## Run the CLI

```bash
poetry run apass create someservice
```

Entry point defined as `apass.cli:app` (Typer app) in `pyproject.toml` (`[project.scripts]`).

## Module map

- `cli.py` — Typer app, entry point, basic CLI commands (`init`, `create`, `get`, `save`, `remove`, `restore`);
  `create` and `save` accept optional `--login` / `-l`; `remove` moves to Recycle Bin
- `vault.py` — `Vault` class backed by **KDBX 4** (pykeepass). Methods: `init_db`, `save`,
  `search`, `read_db`, `store_db`, `remove` (→ Recycle Bin), `restore` (← from Recycle Bin).
  Static helpers `read_db_from_bytes` / `write_db_to_bytes` for sync.
  Data models: `PasswordDB` (has `entries` + `trashed`), `PasswordEntry`
  (has `uuid: UUID`, `name`, `login: str | None`, `password`, `modified: int`).
  Custom exceptions: `VaultNotInitializedError`, `EntryAlreadyExistsError`,
  `EntryNotFoundError`, `CorruptedVaultError`, `WrongPasswordError`.
  Atomic file writes are handled by pykeepass internally (writes to `.tmp` then `rename`).
- `generator.py` — Password generation with configurable size and minimum
  digit/special character guarantees (`create_password`)
- `config.py` — Database path resolution: `APASS_DB_PATH` env var or `~/.apass/vault.kdbx`
- `_atomic_write.py` — `atomic_write_bytes()`: atomic file write via tempfile+fsync+rename
  (still used by sync state and OAuth token files)
- `clipboard.py` — Cross-platform clipboard integration (`pbcopy` / `xclip` / `clip`)
- `sync/` — Cloud storage sync package:
  - `backend.py` — `SyncBackend` Protocol, `OAuthProvider` Protocol, `CloudApiError`, `NotLoggedInError` exceptions
  - `state.py` — `SyncState` dataclass with `backend` field (`gdrive` or `yadisk`),
    `load_sync_state()`, `save_sync_state()`; stores state in `sync.json` next to vault file
  - `merge.py` — `merge_dbs()` function, `MergeResult` dataclass.
  Merge key: entry `uuid` (standard KDBX UUID). LWW by `modified` timestamp;
  `login` is included in equality checks for unchanged detection.
  Trashed entries (KDBX Recycle Bin) are tracked separately and merged with the
  same LWW rule — the side with the newer modification time wins, regardless of
  alive vs. trashed state.
  - `oauth.py` — Google OAuth 2.0 flow and `GoogleOAuthProvider` class;
    stores config in `gdrive_oauth.json` and tokens in `gdrive_token.json` next to vault file
  - `gdrive.py` — `GoogleDriveClient` class implementing `SyncBackend` for Google Drive
  - `yandex_types.py` — `YandexToken` dataclass (shared between yadisk.py and yandex_oauth.py)
  - `yandex_oauth.py` — Yandex OAuth 2.0 flow (port 9000, scopes `cloud_api:disk.read/write`)
    and `YandexOAuthProvider` class; stores config in `yadisk_oauth.json` and tokens
    in `yadisk_token.json` next to vault file
  - `yadisk.py` — `YandexDiskClient` class implementing `SyncBackend` for Yandex Disk
    (vault stored at `/apass/vault.db`)
  - `operations.py` — High-level sync operations (`perform_sync` — bidirectional merge + store + upload; `compute_diff` — dry-run preview; `perform_delete_remote`);
  provider registry (`_PROVIDERS`), `get_provider()` function
  - `sync_cli.py` — CLI commands for sync (`setup`, `login`, `logout`, `status`, `diff`, `run`, `delete-remote`, `backend`)
- `experiments.py` — Scratch/prototyping file (not part of the app)

> **Keep this module map up to date!** When you add, rename, or significantly
> change a module, update its description here so the next agent session has
> accurate context.

## Key facts

- **Python >= 3.14 required** — non-standard, bleeding edge.
- **Poetry 2.x**, build system `poetry-core>=2.0.0`. Source layout: `src/apass/`.
- **No linter, typechecker, or formatter configured.** No CI/CD.
- Tests use `CliRunner` (Typer) + `unittest.mock` (stdlib), no extra mocking library.
