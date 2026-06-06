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

- `cli.py` — Typer app, entry point, all CLI commands (`init`, `create`, `get`, `save`)
- `vault.py` — `Vault` class with `init_db`, `save`, `search`;
  data models (`PasswordDB`, `PasswordEntry`); custom exceptions
  (`VaultNotInitializedError`, `EntryAlreadyExistsError`, `CorruptedVaultError`,
  `WrongPasswordError`, `UnsupportedDBVersionError`); atomic file writes via tempfile+rename
- `crypto.py` — Encryption/decryption primitives: AES-256-GCM + Argon2id KDF,
  self-describing payload envelope (version, salt, KDF params, nonce, ciphertext);
  exceptions `VaultStructureError` and `DecryptionError`
- `generator.py` — Password generation with configurable size and minimum
  digit/special character guarantees (`create_password`)
- `config.py` — Database path resolution: `APASS_DB_PATH` env var or `~/.apass/vault.db`
- `clipboard.py` — Cross-platform clipboard integration (`pbcopy` / `xclip` / `clip`)
- `experiments.py` — Scratch/prototyping file (not part of the app)

> **Keep this module map up to date!** When you add, rename, or significantly
> change a module, update its description here so the next agent session has
> accurate context.

## Key facts

- **Python >= 3.14 required** — non-standard, bleeding edge.
- **Poetry 2.x**, build system `poetry-core>=2.0.0`. Source layout: `src/apass/`.
- **No linter, typechecker, or formatter configured.** No CI/CD.
- Tests use `CliRunner` (Typer) + `unittest.mock` (stdlib), no extra mocking library.
