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
  `create` and `save` accept optional `--login` / `-l`; `remove` and `restore` look up by `name`
  substring and disambiguate interactively when multiple entries match (since
  `(name, login)` is the entry identity at the vault layer)
- `vault/` — KDBX 4 (pykeepass) vault package:
  - `__init__.py` — empty (package marker)
  - `db.py` — `Vault` class (renamed from `__init__.py`). Backed by pykeepass.
    Methods: `init_db`, `save` (with `force` overwrite), `search`
    (case-insensitive substring on title), `remove` (→ Recycle Bin),
    `restore` (← from Recycle Bin), `list_trashed`, `to_bytes`
    (for sync upload), `merge` (sync merge with remote bytes).
    Entry identity is the pair `(name, login)`, so `save` / `remove` /
    `restore` all take `login` as a positional argument. `search` and
    `list_trashed` still match by `name` substring (used by `cli.py` to
    disambiguate before calling `remove` / `restore`).
    Data model: `PasswordEntry` (`name`, `password`, `login: str`) —
    empty `username` in KDBX is normalized to `""`, so `login` is always
    a `str`. Atomic file writes are handled by pykeepass internally
    (writes to `.tmp` then `rename`).
  - `errors.py` — Custom exceptions: `VaultNotInitializedError`,
    `EntryAlreadyExistsError`, `EntryNotFoundError`, `CorruptedVaultError`,
    `WrongPasswordError`.
  - `keepass.py` — pykeepass helpers: `find_alive` / `find_all_alive`,
    `find_trashed` / `find_all_trashed`, `get_all_entries`, `get_title`
    (raises if the KDBX title is empty), `validate_entries` (rejects
    empty titles/passwords at load time). `find_alive` and `find_trashed`
    match on the `(name, login)` pair (the `login` argument is compared
    against `entry.username or ""`).
  - `merge.py` — `MergeResult` dataclass and `merge_dbs()` function.
    Two passes per remote entry: (1) merge by `uuid` (KDBX stable UUID,
    not title) with LWW by `mtime` — trashed entries follow the same LWW
    rule, the side with the newer mtime wins regardless of alive vs.
    trashed state; (2) deduplication by `(title, username)` pair — when
    a remote entry has no uuid match but another local/remote entry
    shares the same `(title, username)`, the older side is renamed with
    a numeric suffix (`_N` based on existing suffix count) and moved to
    the Recycle Bin. `MergeResult` fields carry human-readable strings
    formatted as `title/username` (or just `title` when username is empty),
    not UUIDs.
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
  provider registry (`_PROVIDERS`), `get_provider()` function. Local `RemoteVaultCorruptedError`,
  `NoRemoteVaultError`, `UnsupportedBackendError` exceptions. `VaultNotInitializedError`
  from the vault package propagates as-is.
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
