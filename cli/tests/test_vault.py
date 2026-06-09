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


def test_save_adds_entry(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password)

    # Verify by reading back
    vault2 = Vault(initialized_vault._vault_file)
    db = vault2._read_db(master_password)
    assert len(db.entries) == 1
    assert db.entries[0].name == "example"
    assert db.entries[0].password == "password123"


def test_save_adds_multiple_entries(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example1", "password1", master_password)
    initialized_vault.save("example2", "password2", master_password)
    initialized_vault.save("example3", "password3", master_password)

    # Verify by reading back
    vault2 = Vault(initialized_vault._vault_file)
    db = vault2._read_db(master_password)
    assert [e.name for e in db.entries] == ["example1", "example2", "example3"]


def test_save_raises_on_duplicate(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password)

    with pytest.raises(EntryAlreadyExistsError):
        initialized_vault.save("example", "password456", master_password)


def test_read_db_raises_when_not_initialized(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)

    with pytest.raises(VaultNotInitializedError):
        vault._read_db("master123")


def test_read_db_raises_on_wrong_password(initialized_vault: Vault) -> None:
    with pytest.raises(WrongPasswordError):
        initialized_vault._read_db("wrongpassword")


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


def test_search_multiple_entries(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("some pass", "passwd1", master_password)
    initialized_vault.save("Example1", "passwd2", master_password)
    initialized_vault.save("example2", "passwd3", master_password)
    initialized_vault.save("Unknown", "passwd4", master_password)
    initialized_vault.save("example_3", "passwd5", master_password)
    initialized_vault.save("Some example", "passwd6", master_password)
    initialized_vault.save("fooexamplebar", "passwd7", master_password)
    initialized_vault.save("Another pass", "passwd8", master_password)

    entries = initialized_vault.search("example", master_password)

    assert [e.name for e in entries] == ["Example1", "example2", "example_3", "Some example", "fooexamplebar"]


def test_search_no_entries(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("some pass 1", "passwd1", master_password)
    initialized_vault.save("some pass 2", "passwd2", master_password)

    entries = initialized_vault.search("example", master_password)

    assert len(entries) == 0
