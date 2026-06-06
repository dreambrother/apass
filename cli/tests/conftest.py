from pathlib import Path
import random
import string

from apass.vault import Vault
import pytest


@pytest.fixture
def vault_file(tmp_path: Path) -> Path:
    return tmp_path / "vault.db"


@pytest.fixture
def master_password() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


@pytest.fixture
def initialized_vault(vault_file: Path, master_password: str) -> Vault:
    vault = Vault(vault_file)
    vault.init_db(master_password)
    return vault


@pytest.fixture(autouse=True)
def isolated_db_path(monkeypatch: pytest.MonkeyPatch, vault_file: Path) -> None:
    monkeypatch.setenv("APASS_DB_PATH", str(vault_file))
