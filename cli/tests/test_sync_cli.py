from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from apass.cli import app

runner = CliRunner()


def test_sync_status_not_logged_in() -> None:
    mock_provider = MagicMock()
    mock_provider.is_logged_in.return_value = False
    mock_provider.get_display_name.return_value = "Google Drive"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
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
    mock_provider = MagicMock()
    mock_provider.is_logged_in.return_value = True
    mock_provider.get_display_name.return_value = "Google Drive"

    mock_state = MagicMock()
    mock_state.account_email = "user@example.com"
    mock_state.remote_file_id = "file123"
    mock_state.last_sync_at = 1234567890

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.sync_cli.load_sync_state", return_value=mock_state),
    ):
        result = runner.invoke(app, ["sync", "status"])

    assert result.exit_code == 0
    assert "user@example.com" in result.output
    assert "file123" in result.output


def test_sync_setup_saves_config() -> None:
    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"

    with (
        patch("apass.sync.operations._PROVIDERS", {"gdrive": mock_provider}),
        patch("apass.sync.sync_cli.load_sync_state") as mock_load_state,
        patch("apass.sync.sync_cli.save_sync_state") as mock_save_state,
    ):
        mock_state = MagicMock()
        mock_load_state.return_value = mock_state

        result = runner.invoke(app, ["sync", "setup"], input="client123\nsecret456\n")

    assert result.exit_code == 0
    assert "OAuth credentials saved" in result.output
    mock_provider.save_config.assert_called_once_with("client123", "secret456")
    mock_save_state.assert_called_once()


def test_sync_login_no_config() -> None:
    mock_provider = MagicMock()
    mock_provider.load_config.return_value = False

    with patch("apass.sync.operations.get_provider", return_value=mock_provider):
        result = runner.invoke(app, ["sync", "login"])

    assert result.exit_code == 1
    assert "not configured" in result.output


def test_sync_logout() -> None:
    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.sync_cli.load_sync_state") as mock_load_state,
        patch("apass.sync.sync_cli.save_sync_state") as mock_save_state,
    ):
        mock_state = MagicMock()
        mock_state.backend = "gdrive"
        mock_load_state.return_value = mock_state

        result = runner.invoke(app, ["sync", "logout"])

    assert result.exit_code == 0
    assert "Logged out" in result.output
    mock_provider.delete_credentials.assert_called_once()
    mock_save_state.assert_called_once()


def test_sync_diff_no_remote() -> None:
    mock_vault = MagicMock()
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "diff"], input="master123\n")

    assert result.exit_code == 0
    assert "No remote vault" in result.output


def test_sync_run_first_time() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None
    mock_client.upload_vault_file.return_value = "new_file_id"

    mock_vault = MagicMock()
    mock_db = MagicMock()
    mock_db.ver = 1
    mock_db.entries = [MagicMock()]
    mock_db.serialize.return_value = b'{"ver": 1, "entries": []}'
    mock_vault.read_db.return_value = mock_db

    mock_state = MagicMock()
    mock_state.remote_file_id = None

    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "run"], input="master123\n")

    assert result.exit_code == 0
    assert "Synced with Google Drive" in result.output
    mock_client.upload_vault_file.assert_called_once()
    mock_vault.store_db.assert_called_once()
    mock_save_state.assert_called_once()


def test_sync_run_no_local_vault() -> None:
    from apass.vault import VaultNotInitializedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"
    mock_client.upload_vault_file.return_value = "remote_file_id"

    mock_vault = MagicMock()
    mock_vault.read_db.side_effect = VaultNotInitializedError()

    mock_db = MagicMock()
    mock_db.ver = 1
    mock_db.entries = [MagicMock()]
    mock_db.serialize.return_value = b'{"ver": 1, "entries": []}'

    mock_merge_result = MagicMock()
    mock_merge_result.added = []
    mock_merge_result.updated = []
    mock_merge_result.kept_locally_only = []
    mock_merge_result.kept_local_with_conflict = []
    mock_merge_result.unchanged_count = 0
    mock_merge_result.merged_db = mock_db

    mock_state = MagicMock()
    mock_state.remote_file_id = None

    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations._decrypt_remote_vault", return_value=mock_db),
        patch("apass.sync.operations.merge_dbs", return_value=mock_merge_result),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "run"], input="master123\n")

    assert result.exit_code == 0
    assert "Synced with Google Drive" in result.output
    mock_vault.store_db.assert_called_once()
    mock_client.upload_vault_file.assert_called_once()
    mock_save_state.assert_called_once()


def test_sync_run_both_empty() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None

    mock_vault = MagicMock()
    mock_db = MagicMock()
    mock_db.entries = []
    mock_vault.read_db.return_value = mock_db

    mock_state = MagicMock()
    mock_state.remote_file_id = None

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "run"], input="master123\n")

    assert result.exit_code == 1
    assert "Nothing to sync" in result.output


def test_sync_run_both_exist_merges_and_uploads() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"
    mock_client.upload_vault_file.return_value = "new_file_id"

    mock_vault = MagicMock()
    local_db = MagicMock()
    local_db.ver = 1
    local_db.entries = [MagicMock()]
    local_db.serialize.return_value = b'{"ver": 1, "entries": []}'
    mock_vault.read_db.return_value = local_db

    remote_db = MagicMock()
    remote_db.ver = 1
    remote_db.entries = [MagicMock()]

    mock_merge_result = MagicMock()
    mock_merge_result.added = []
    mock_merge_result.updated = []
    mock_merge_result.kept_locally_only = []
    mock_merge_result.kept_local_with_conflict = []
    mock_merge_result.unchanged_count = 1
    mock_merge_result.merged_db = local_db

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations._decrypt_remote_vault", return_value=remote_db),
        patch("apass.sync.operations.merge_dbs", return_value=mock_merge_result),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "run"], input="master123\n")

    assert result.exit_code == 0
    assert "Synced with Google Drive" in result.output
    assert "new_file_id" in result.output
    mock_vault.store_db.assert_called_once()
    mock_client.upload_vault_file.assert_called_once()
    mock_save_state.assert_called_once()


def test_sync_diff_no_local_vault() -> None:
    from apass.vault import VaultNotInitializedError

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

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations._decrypt_remote_vault", return_value=mock_db),
        patch("apass.sync.operations.merge_dbs", return_value=mock_merge_result),
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "diff"], input="master123\n")

    assert result.exit_code == 0
    assert "Sync preview" in result.output


def test_sync_delete_remote_success() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_data"

    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"
    mock_provider.get_authenticated_client.return_value = mock_client

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state") as mock_save_state,
        patch("apass.sync.operations._decrypt_remote_vault"),
    ):
        result = runner.invoke(app, ["sync", "delete-remote", "--yes"], input="master123\n")

    assert result.exit_code == 0
    assert "Remote vault deleted" in result.output
    mock_client.delete_vault_file.assert_called_once_with("remote_file_id")
    assert mock_state.remote_file_id is None
    assert mock_state.last_sync_at is None
    mock_save_state.assert_called_once()


def test_sync_delete_remote_with_confirm_yes() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_data"

    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"
    mock_provider.get_authenticated_client.return_value = mock_client

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations.save_sync_state"),
        patch("apass.sync.operations._decrypt_remote_vault"),
    ):
        result = runner.invoke(app, ["sync", "delete-remote"], input="master123\ny\n")

    assert result.exit_code == 0
    assert "Remote vault deleted" in result.output
    mock_client.delete_vault_file.assert_called_once()


def test_sync_delete_remote_cancelled() -> None:
    mock_provider = MagicMock()
    mock_provider.get_display_name.return_value = "Google Drive"

    with patch("apass.sync.operations.get_provider", return_value=mock_provider):
        result = runner.invoke(app, ["sync", "delete-remote"], input="master123\nn\n")

    assert result.exit_code == 1
    assert "Aborted" in result.output


def test_sync_delete_remote_no_remote() -> None:
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    mock_state = MagicMock()
    mock_state.remote_file_id = None

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
    ):
        result = runner.invoke(app, ["sync", "delete-remote", "--yes"], input="master123\n")

    assert result.exit_code == 1
    assert "No remote vault" in result.output


def test_sync_delete_remote_wrong_password() -> None:
    from apass.sync.operations import RemoteVaultCorruptedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_data"

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations._decrypt_remote_vault", side_effect=RemoteVaultCorruptedError("Wrong password")),
    ):
        result = runner.invoke(app, ["sync", "delete-remote", "--yes"], input="wrongpass\n")

    assert result.exit_code == 1
    assert "Wrong password" in result.output
    mock_client.delete_vault_file.assert_not_called()


def test_sync_delete_remote_cloud_error() -> None:
    from apass.sync.backend import CloudApiError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_data"
    mock_client.delete_vault_file.side_effect = CloudApiError("API error")

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.operations.load_sync_state", return_value=mock_state),
        patch("apass.sync.operations._decrypt_remote_vault"),
    ):
        result = runner.invoke(app, ["sync", "delete-remote", "--yes"], input="master123\n")

    assert result.exit_code == 1
    assert "API error" in result.output
