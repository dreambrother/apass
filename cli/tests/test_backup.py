from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

import apass.sync.backup as backup_mod
from apass.sync.backup import MAX_BACKUPS, create_backup


@contextmanager
def _isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(backup_mod, "APASS_DIR", tmp_path)
    yield backup_root


def test_create_backup_returns_none_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _isolated_backup_dir(tmp_path, monkeypatch):
        result = create_backup(tmp_path / "missing.kdbx")

    assert result is None


def test_create_backup_writes_copy_with_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_file = tmp_path / "vault.kdbx"
    vault_file.write_bytes(b"encrypted-blob")

    with _isolated_backup_dir(tmp_path, monkeypatch):
        result = create_backup(vault_file, now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC))

    assert result is not None
    assert result.exists()
    assert result.read_bytes() == b"encrypted-blob"
    mode = result.stat().st_mode & 0o777
    assert mode == 0o600
    assert result.name.startswith("vault-")
    assert result.name.endswith(".kdbx")


def test_create_backup_creates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _isolated_backup_dir(tmp_path, monkeypatch) as backup_root:
        vault_file = tmp_path / "vault.kdbx"
        vault_file.write_bytes(b"data")

        result = create_backup(vault_file, now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC))

        assert backup_root.exists()
        assert result is not None and result.exists()


def test_create_backup_prunes_to_max(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _isolated_backup_dir(tmp_path, monkeypatch) as backup_root:
        backup_root.mkdir(parents=True, exist_ok=True)
        vault_file = tmp_path / "vault.kdbx"
        vault_file.write_bytes(b"data")

        for i in range(MAX_BACKUPS + 3):
            stamp = datetime(2025, 1, 1, 0, 0, i, tzinfo=UTC)
            (backup_root / f"vault-{stamp.strftime('%Y%m%d-%H%M%S')}.kdbx").write_bytes(b"x")

        create_backup(vault_file, now=datetime(2025, 2, 1, 0, 0, 0, tzinfo=UTC))

        remaining = sorted(p.name for p in backup_root.iterdir())
        assert len(remaining) == MAX_BACKUPS
        assert remaining[-1] == "vault-20250201-000000.kdbx"


def test_create_backup_ignores_non_backup_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _isolated_backup_dir(tmp_path, monkeypatch) as backup_root:
        vault_file = tmp_path / "vault.kdbx"
        vault_file.write_bytes(b"data")
        backup_root.mkdir(parents=True, exist_ok=True)
        (backup_root / "notes.txt").write_bytes(b"hi")

        create_backup(vault_file, now=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC))

        assert (backup_root / "notes.txt").exists()