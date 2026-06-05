import pytest


@pytest.fixture(autouse=True)
def isolated_db_path(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("APASS_DB_PATH", str(tmp_path / "vault.db"))
