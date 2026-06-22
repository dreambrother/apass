import json
from pathlib import Path
from unittest.mock import patch

from apass.sync.state import SyncState, load_sync_state, save_sync_state


def test_load_sync_state_no_file(tmp_path: Path) -> None:
    with patch("apass.sync.state.get_db_path", return_value=tmp_path / "vault.db"):
        state = load_sync_state()

    assert state.remote_file_id is None
    assert state.account_email is None
    assert state.last_sync_at is None


def test_save_and_load_sync_state(tmp_path: Path) -> None:
    with patch("apass.sync.state.get_db_path", return_value=tmp_path / "vault.db"):
        state = SyncState(
            remote_file_id="abc123",
            account_email="user@example.com",
            last_sync_at=1234567890,
        )
        save_sync_state(state)

        loaded = load_sync_state()

    assert loaded.remote_file_id == "abc123"
    assert loaded.account_email == "user@example.com"
    assert loaded.last_sync_at == 1234567890


def test_save_sync_state_creates_file_with_correct_permissions(tmp_path: Path) -> None:
    with patch("apass.sync.state.get_db_path", return_value=tmp_path / "vault.db"):
        state = SyncState(remote_file_id="test")
        save_sync_state(state)

    state_file = tmp_path / "sync.json"
    assert state_file.exists()

    import os
    mode = os.stat(state_file).st_mode & 0o777
    assert mode == 0o600


def test_save_sync_state_atomic_write(tmp_path: Path) -> None:
    with patch("apass.sync.state.get_db_path", return_value=tmp_path / "vault.db"):
        state1 = SyncState(remote_file_id="first")
        save_sync_state(state1)

        state2 = SyncState(remote_file_id="second")
        save_sync_state(state2)

        loaded = load_sync_state()

    assert loaded.remote_file_id == "second"


def test_sync_state_is_configured() -> None:
    state1 = SyncState()
    assert not state1.is_configured

    state2 = SyncState(remote_file_id="abc")
    assert state2.is_configured


def test_load_sync_state_handles_partial_data(tmp_path: Path) -> None:
    state_file = tmp_path / "sync.json"
    state_file.write_text(json.dumps({"remote_file_id": "test"}))

    with patch("apass.sync.state.get_db_path", return_value=tmp_path / "vault.db"):
        state = load_sync_state()

    assert state.remote_file_id == "test"
    assert state.account_email is None
    assert state.last_sync_at is None
