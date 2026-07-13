from unittest.mock import MagicMock, patch

from apass.vault.merge import MergeResult
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
    remote_bytes = b"kdbx_bytes"
    created_remote_file_id = "new_file_id"

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None
    mock_client.upload_vault_file.return_value = created_remote_file_id

    mock_vault = MagicMock()
    mock_vault.merge.return_value = MergeResult()
    mock_vault.to_bytes.return_value = remote_bytes

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
    mock_client.upload_vault_file.assert_called_with(remote_bytes, None)
    mock_save_state.assert_called_once_with(mock_state)


def test_sync_run_no_local_vault() -> None:
    from apass.vault.errors import VaultNotInitializedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"
    mock_client.upload_vault_file.return_value = "remote_file_id"

    mock_vault = MagicMock()
    mock_vault.merge.side_effect = VaultNotInitializedError()

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

    assert result.exit_code == 1
    assert "Vault is not initialized" in result.output
    mock_vault.merge.assert_called_once()
    mock_client.upload_vault_file.assert_not_called()
    mock_save_state.assert_not_called()


def test_sync_run_both_empty() -> None:
    payload = b"empty_kdbx"
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = None
    mock_client.upload_vault_file.return_value = "new_file_id"

    mock_vault = MagicMock()
    mock_vault.merge.return_value = MergeResult()
    mock_vault.to_bytes.return_value = payload

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
    # Local is empty and there is no remote: merge is skipped,
    # and a fresh empty vault is uploaded.
    mock_vault.merge.assert_not_called()
    mock_vault.to_bytes.assert_called_once_with("master123")
    mock_client.upload_vault_file.assert_called_once_with(payload, None)
    mock_save_state.assert_called_once_with(mock_state)


def test_sync_run_both_exist_merges_and_uploads() -> None:
    payload = b"kdbx_bytes"
    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"
    mock_client.upload_vault_file.return_value = "new_file_id"

    mock_vault = MagicMock()
    mock_vault.merge.return_value = MergeResult(
        added=["gmail"],
        updated=["github"],
        trashed=["oldaccount"],
        added_to_trash=["dead_service"],
        updated_in_trash=["trashed_one"],
        restored_from_trash=["resurrected"],
    )
    mock_vault.to_bytes.return_value = payload

    mock_state = MagicMock()
    mock_state.remote_file_id = "remote_file_id"

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
    assert "new_file_id" in result.output
    assert "Added from remote: gmail" in result.output
    assert "Updated: github" in result.output
    assert "Trashed: oldaccount" in result.output
    assert "Added to trash: dead_service" in result.output
    assert "Updated in trash: trashed_one" in result.output
    assert "Restored from trash: resurrected" in result.output
    mock_vault.merge.assert_called_once()
    mock_vault.to_bytes.assert_called_once_with("master123")
    mock_client.upload_vault_file.assert_called_once_with(payload, "remote_file_id")
    mock_save_state.assert_called_once_with(mock_state)


def test_sync_diff_no_local_vault() -> None:
    from apass.vault.errors import VaultNotInitializedError

    mock_client = MagicMock()
    mock_client.find_vault_file.return_value = "remote_file_id"
    mock_client.download_vault_file.return_value = b"encrypted_remote"

    mock_vault = MagicMock()
    mock_vault.merge.side_effect = VaultNotInitializedError()

    mock_provider = MagicMock()
    mock_provider.get_authenticated_client.return_value = mock_client

    with (
        patch("apass.sync.operations.get_provider", return_value=mock_provider),
        patch("apass.sync.sync_cli.Vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["sync", "diff"], input="master123\n")

    assert result.exit_code == 1
    assert "Vault is not initialized" in result.output
    mock_vault.merge.assert_called_once()


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
        patch("apass.sync.operations.keepass.is_valid", return_value=True),
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
        patch("apass.sync.operations.keepass.is_valid", return_value=True),
    ):
        result = runner.invoke(app, ["sync", "delete-remote"], input="master123\ny\n")

    assert result.exit_code == 0
    assert "Remote vault deleted" in result.output
    mock_client.delete_vault_file.assert_called_once_with("remote_file_id")


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
        patch("apass.sync.operations.keepass.is_valid", return_value=False),
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
        patch("apass.sync.operations.keepass.is_valid", return_value=True),
    ):
        result = runner.invoke(app, ["sync", "delete-remote", "--yes"], input="master123\n")

    assert result.exit_code == 1
    assert "API error" in result.output
