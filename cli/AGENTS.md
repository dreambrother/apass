# AGENTS.md — apass

## Setup

```bash
poetry install
```

## Run tests

```bash
poetry run pytest
poetry run pytest tests/test_cli.py::test_name  # single test
```

## Run the CLI

```bash
poetry run apass create someservice
```

Entry point: `apass.cli:app` (Typer).

## Module map

- `cli.py` — main CLI handlers: init, create, get, save, remove, restore
- `sync/sync_cli.py` — sync subcommand handlers: setup, login, logout, status, diff, run, delete-remote, backend
- `vault/` — KDBX 4 vault (pykeepass): db, errors, keepass helpers, merge
- `generator.py` — password generation
- `config.py` — DB path resolution (`APASS_DB_PATH` or `~/.apass/vault.kdbx`)
- `_atomic_write.py` — atomic file writes
- `clipboard.py` — cross-platform clipboard
- `sync/` — cloud sync: Google Drive, Yandex Disk, OAuth, state, operations
- `experiments.py` — scratch file (not part of the app)

## Key facts

- Python >= 3.14, Poetry 2.x, source layout `src/apass/`
- No linter, typechecker, formatter, or CI/CD
- Tests: `CliRunner` + `unittest.mock` (stdlib)
