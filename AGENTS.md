# AGENTS.md — apass

## Workspace

All code lives under `cli/`. Run every command from `cli/`:

```bash
cd cli
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
poetry run pytest tests/test_cli.py::test_generate_prompts_for_password_and_stores
```

## Run the CLI

```bash
poetry run apass generate someservice
```

Entry point defined as `apass.cli:app` (Typer app) in `pyproject.toml` (`[project.scripts]`).

## Key facts

- **Python >= 3.14 required** — non-standard, bleeding edge.
- **Poetry 2.x**, build system `poetry-core>=2.0.0`. Source layout: `src/apass/`.
- **No linter, typechecker, or formatter configured.** No CI/CD.
- `clipboard.py` shells out to `pbcopy` (macOS), `xclip` (Linux), or `clip` (Windows). Tests mock this.
- `vault.store()` is a stub — does nothing yet. Vault directory: `~/.apass/`.
- `generator.generate_password()` uses `random.choices` (not `secrets`). 10 chars, alphanumeric only.
- Tests use `pytest-mock` (`MockerFixture`).
