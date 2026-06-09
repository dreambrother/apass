from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from apass.cli import app

runner = CliRunner()


def test_sync_status_not_logged_in() -> None:
    with (
        patch("apass.sync.sync_cli.load_credentials", return_value=None),
        patch("apass.sync.sync_cli.load_sync_state") as mock_load_state,
    ):
        mock_state = MagicMock()
        mock_state.account_email = None
        mock_state.remote_file_id = None
        mock_state.last_sync_at = None
        mock_load_state.return_value = mock_state

        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "Not logged in" in result.output


def test_sync_status_logged_in() -> None:
    mock_creds = MagicMock()
    mock_state = MagicMock()
    mock_state.account_email = "user@example.com"
    mock_state.remote_file_id = "file123"
    mock_state.last_sync_at = 1234567890

    with (
        patch("apass.sync.sync_cli.load_credentials", return_value=mock_creds),
        patch("apass.sync.sync_cli.load_sync_state", return_value=mock_state),
    ):
        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "user@example.com" in result.output
    assert "file123" in result.output


def test_sync_setup_saves_config() -> None:
    with patch("apass.sync.sync_cli.save_oauth_config") as mock_save:
        result = runner.invoke(app, ["sync", "setup"], input="client123\nsecret456\n")

    assert result.exit_code == 0
    assert "OAuth credentials saved" in result.output
    mock_save.assert_called_once()


def test_sync_login_no_config() -> None:
    with patch("apass.sync.sync_cli.load_oauth_config", return_value=None):
        result = runner.invoke(app, ["sync", "login"])

    assert result.exit_code == 1
    assert "not configured" in result.output


def test_sync_logout() -> None:
    with (
        patch("apass.sync.sync_cli.delete_credentials") as mock_delete,
        patch("apass.sync.sync_cli.save_sync_state") as mock_save,
    ):
        result = runner.invoke(app, ["sync", "logout"])

    assert result.exit_code == 0
    assert "Logged out" in result.output
    mock_delete.assert_called_once()
    mock_save.assert_called_once()


def test_sync_diff_no_remote() -> None:
    mock_vault = MagicMock()

    with (
        patch("apass.sync.operations.load_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.refresh_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.GoogleDriveClient") as mock_client_class,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        mock_client = MagicMock()
        mock_client.find_vault_file.return_value = None
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["sync", "diff"], input="master123\n")

    assert result.exit_code == 0
    assert "No remote vault" in result.output


def test_sync_push_first_time() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None
    mock_client.upload_vault_file.return_value = "new_file_id"

    mock_vault = MagicMock()
    mock_db = MagicMock()
    mock_db.ver = 1
    mock_db.entries = []
    mock_db.serialize.return_value = b'{"ver": 1, "entries": []}'
    mock_vault.read_db.return_value = mock_db

    mock_state = MagicMock()
    mock_state.remote_file_id = None

    with (
        patch("apass.sync.operations.load_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.refresh_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.GoogleDriveClient", return_value=mock_client),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "push"], input="master123\n")

    assert result.exit_code == 0
    assert "Synced with Google Drive" in result.output
    mock_client.upload_vault_file.assert_called_once()
    mock_save_state.assert_called_once()


def test_sync_diff_no_local_vault() -> None:
    from apass.vault import PasswordDB, VaultNotInitializedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"

    mock_vault = MagicMock()
    mock_vault.read_db.side_effect = VaultNotInitializedError()

    mock_db = MagicMock()
    mock_db.ver = 1
    mock_db.entries = []

    mock_merge_result = MagicMock()
    mock_merge_result.added = []
    mock_merge_result.updated = []
    mock_merge_result.kept_locally_only = []
    mock_merge_result.kept_local_with_conflict = []
    mock_merge_result.unchanged_count = 0

    with (
        patch("apass.sync.operations.load_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.refresh_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.GoogleDriveClient", return_value=mock_client),
        patch("apass.sync.operations._decrypt_remote_vault", return_value=mock_db),
        patch("apass.sync.operations.merge_dbs", return_value=mock_merge_result),
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "diff"], input="master123\n")

    assert result.exit_code == 0
    assert "Sync preview" in result.output


def test_sync_pull_no_remote() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None

    with (
        patch("apass.sync.operations.load_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.refresh_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.GoogleDriveClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["sync", "pull"], input="master123\n")

    assert result.exit_code == 1
    assert "No remote vault" in result.output


def test_sync_pull_no_local_vault() -> None:
    from apass.vault import PasswordDB, VaultNotInitializedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"

    mock_vault = MagicMock()
    mock_vault.read_db.side_effect = VaultNotInitializedError()

    mock_db = MagicMock()
    mock_db.ver = 1
    mock_db.entries = []
    mock_db.serialize.return_value = b'{"ver": 1, "entries": []}'

    mock_merge_result = MagicMock()
    mock_merge_result.added = []
    mock_merge_result.updated = []
    mock_merge_result.kept_locally_only = []
    mock_merge_result.kept_local_with_conflict = []
    mock_merge_result.unchanged_count = 0
    mock_merge_result.merged_db = mock_db

    with (
        patch("apass.sync.operations.load_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.refresh_credentials", return_value=MagicMock()),
        patch("apass.sync.operations.GoogleDriveClient", return_value=mock_client),
        patch("apass.sync.operations._decrypt_remote_vault", return_value=mock_db),
        patch("apass.sync.operations.merge_dbs", return_value=mock_merge_result),
        patch("apass.sync.operations.load_sync_state") as mock_load_state,
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        mock_state = MagicMock()
        mock_state.remote_file_id = None
        mock_load_state.return_value = mock_state

        result = runner.invoke(app, ["sync", "pull"], input="master123\n")

    assert result.exit_code == 0
    assert "Synced with Google Drive" in result.output
    mock_vault.store_db.assert_called_once()
    mock_save_state.assert_called_once()
