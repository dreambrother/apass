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

- `cli.py` — Typer app, entry point, basic CLI commands (`init`, `create`, `get`, `save`)
- `vault.py` — `Vault` class with `init_db`, `save`, `search`, `read_db`, `store_db`;
  data models (`PasswordDB`, `PasswordEntry`); custom exceptions
  (`VaultNotInitializedError`, `EntryAlreadyExistsError`, `CorruptedVaultError`,
  `WrongPasswordError`, `UnsupportedDBVersionError`); atomic file writes via tempfile+rename
- `crypto.py` — Encryption/decryption primitives: AES-256-GCM + Argon2id KDF,
  self-describing payload envelope (version, salt, KDF params, nonce, ciphertext);
  exceptions `VaultStructureError` and `DecryptionError`
- `generator.py` — Password generation with configurable size and minimum
  digit/special character guarantees (`create_password`)
- `config.py` — Database path resolution: `APASS_DB_PATH` env var or `~/.apass/vault.db`
- `_atomic_write.py` — `atomic_write_bytes()`: atomic file write via tempfile+fsync+rename
- `clipboard.py` — Cross-platform clipboard integration (`pbcopy` / `xclip` / `clip`)
- `sync/` — Google Drive sync package:
  - `state.py` — `SyncState` dataclass, `load_sync_state()`, `save_sync_state()`;
    stores state in `sync.json` next to vault file
  - `merge.py` — `merge_dbs()` function, `MergeResult` dataclass (LWW by `name` + `modified`)
  - `oauth.py` — Google OAuth 2.0 flow (`drive.appfolder` scope);
    stores config in `gdrive_oauth.json` and tokens in `gdrive_token.json` next to vault file
  - `gdrive.py` — `GoogleDriveClient` class for vault file operations
  - `operations.py` — High-level sync operations (`perform_push`, `perform_pull`, `compute_diff`)
  - `sync_cli.py` — CLI commands for sync (`setup`, `login`, `logout`, `status`, `diff`, `push`, `pull`)
- `experiments.py` — Scratch/prototyping file (not part of the app)

> **Keep this module map up to date!** When you add, rename, or significantly
> change a module, update its description here so the next agent session has
> accurate context.

## Key facts

- **Python >= 3.14 required** — non-standard, bleeding edge.
- **Poetry 2.x**, build system `poetry-core>=2.0.0`. Source layout: `src/apass/`.
- **No linter, typechecker, or formatter configured.** No CI/CD.
- Tests use `CliRunner` (Typer) + `unittest.mock` (stdlib), no extra mocking library.
