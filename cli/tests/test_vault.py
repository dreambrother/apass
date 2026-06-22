from pathlib import Path

import pytest

from apass.vault import (
    CorruptedVaultError,
    EntryAlreadyExistsError,
    EntryNotFoundError,
    Vault,
    VaultNotInitializedError,
    WrongPasswordError,
)


def test_init_db_creates_new_vault(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)

    vault.init_db("master123")

    assert vault_file.exists()


def test_save_adds_entry(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password)

    vault2 = Vault(initialized_vault._vault_file)
    entries = vault2.search("", master_password)
    assert len(entries) == 1
    assert entries[0].name == "example"
    assert entries[0].login is None
    assert entries[0].password == "password123"


def test_save_adds_entry_with_login(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password, "example_user")

    vault2 = Vault(initialized_vault._vault_file)
    entries = vault2.search("", master_password)
    assert len(entries) == 1
    assert entries[0].name == "example"
    assert entries[0].login == "example_user"
    assert entries[0].password == "password123"


def test_save_adds_multiple_entries(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example1", "password1", master_password)
    initialized_vault.save("example2", "password2", master_password)
    initialized_vault.save("example3", "password3", master_password)

    vault2 = Vault(initialized_vault._vault_file)
    entries = vault2.search("", master_password)
    assert [e.name for e in entries] == ["example1", "example2", "example3"]


def test_save_raises_on_duplicate(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password)

    with pytest.raises(EntryAlreadyExistsError):
        initialized_vault.save("example", "password456", master_password)


def test_save_forced(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "password123", master_password)
    initialized_vault.save("example", "password456", master_password, "example_login", force=True)

    vault = Vault(initialized_vault._vault_file)
    entries = vault.search("", master_password)
    assert len(entries) == 1
    assert entries[0].name == "example"
    assert entries[0].login == "example_login"
    assert entries[0].password == "password456"


def test_read_db_raises_when_not_initialized(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault = Vault(vault_file)

    with pytest.raises(VaultNotInitializedError):
        vault.search("", "master123")


def test_read_db_raises_on_wrong_password(initialized_vault: Vault) -> None:
    with pytest.raises(WrongPasswordError):
        initialized_vault.search("", "wrongpassword")


def test_read_db_raises_on_corrupted_file(tmp_path: Path) -> None:
    vault_file = tmp_path / "test.vault"
    vault_file.write_bytes(b"corrupted data")
    vault = Vault(vault_file)

    with pytest.raises(CorruptedVaultError):
        vault.search("", "master123")


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


def test_search_excludes_trashed(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("example", "passwd1", master_password)
    initialized_vault.save("exampletwo", "passwd2", master_password)
    initialized_vault.remove("exampletwo", master_password)

    entries = initialized_vault.search("example", master_password)

    assert [e.name for e in entries] == ["example"]


def test_remove_moves_to_trash(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("utility1", "passwd1", master_password)
    initialized_vault.save("utility2", "passwd2", master_password)
    initialized_vault.save("utility3", "passwd3", master_password)

    initialized_vault.remove("utility2", master_password)

    alive = Vault(initialized_vault._vault_file).search("", master_password)
    trashed = Vault(initialized_vault._vault_file).list_trashed("", master_password)
    assert [e.name for e in alive] == ["utility1", "utility3"]
    assert [e.name for e in trashed] == ["utility2"]


def test_remove_multiple(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("utility1", "passwd1", master_password)
    initialized_vault.save("utility2", "passwd2", master_password)
    initialized_vault.save("utility3", "passwd3", master_password)
    initialized_vault.save("utility4", "passwd4", master_password)

    initialized_vault.remove("utility2", master_password)
    initialized_vault.remove("utility4", master_password)

    alive = Vault(initialized_vault._vault_file).search("", master_password)
    trashed = Vault(initialized_vault._vault_file).list_trashed("", master_password)
    assert [e.name for e in alive] == ["utility1", "utility3"]
    assert [e.name for e in trashed] == ["utility2", "utility4"]


def test_remove_not_found(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("utility1", "passwd1", master_password)
    initialized_vault.save("utility3", "passwd2", master_password)

    with pytest.raises(EntryNotFoundError):
        initialized_vault.remove("utility2", master_password)


def test_restore(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("utility1", "passwd1", master_password)
    initialized_vault.save("utility2", "passwd2", master_password)
    initialized_vault.remove("utility2", master_password)

    initialized_vault.restore("utility2", master_password)

    alive = Vault(initialized_vault._vault_file).search("", master_password)
    trashed = Vault(initialized_vault._vault_file).list_trashed("", master_password)
    assert [e.name for e in alive] == ["utility1", "utility2"]
    assert trashed == []


def test_restore_not_found(initialized_vault: Vault, master_password: str) -> None:
    initialized_vault.save("utility1", "passwd1", master_password)
    initialized_vault.remove("utility1", master_password)

    with pytest.raises(EntryNotFoundError):
        initialized_vault.restore("utility2", master_password)
