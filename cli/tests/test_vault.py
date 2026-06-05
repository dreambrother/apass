import json
from pathlib import Path

import pytest

from apass.crypto import encrypt
from apass.vault import (
    CorruptedVaultError,
    EntryAlreadyExistsError,
    UnsupportedDBVersionError,
    Vault,
    VaultNotInitializedError,
    WrongPasswordError,
)


@pytest.fixture(autouse=True)
def fast_argon2(monkeypatch: pytest.MonkeyPatch) -> None:
    import apass.crypto as c

    monkeypatch.setattr(c, "DEFAULT_ARGON2_MEMORY", 8)
    monkeypatch.setattr(c, "DEFAULT_ARGON2_ITERATIONS", 1)
    monkeypatch.setattr(c, "DEFAULT_ARGON2_LANES", 1)


def test_init_db_creates_new_vault(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)
    
    vault.init_db("master123")
    
    assert vault_file.exists()


def test_create_adds_entry(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)
    vault.init_db("master123")
    
    vault.create("example", "password123", "master123")
    
    # Verify by reading back
    vault2 = Vault(vault_file)
    db = vault2._read_db("master123")
    assert len(db.entries) == 1
    assert db.entries[0].name == "example"
    assert db.entries[0].password == "password123"


def test_create_raises_on_duplicate(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)
    vault.init_db("master123")
    vault.create("example", "password123", "master123")
    
    with pytest.raises(EntryAlreadyExistsError):
        vault.create("example", "password456", "master123")


def test_read_db_raises_when_not_initialized(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)
    
    with pytest.raises(VaultNotInitializedError):
        vault._read_db("master123")


def test_read_db_raises_on_wrong_password(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)
    vault.init_db("master123")
    
    with pytest.raises(WrongPasswordError):
        vault._read_db("wrongpassword")


def test_read_db_raises_on_corrupted_file(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault_file.write_bytes(b"corrupted data")
    vault = Vault(vault_file)
    
    with pytest.raises(CorruptedVaultError):
        vault._read_db("master123")


def test_read_db_raises_on_unsupported_version(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    # Create a vault with unsupported version
    data = {"ver": 999, "entries": []}
    plaintext = json.dumps(data).encode("utf-8")
    payload = encrypt(plaintext, "master123")
    vault_file.write_bytes(payload)
    
    vault = Vault(vault_file)
    with pytest.raises(UnsupportedDBVersionError) as exc_info:
        vault._read_db("master123")
    assert exc_info.value.found_version == 999
