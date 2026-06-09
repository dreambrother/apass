from collections.abc import Iterator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from yadisk.exceptions import PathNotFoundError

from apass.sync.backend import CloudApiError
from apass.sync.yadisk import YandexDiskClient
from apass.sync.yandex_types import YandexToken


@pytest.fixture
def mock_token() -> YandexToken:
    return YandexToken(access_token="test_token")


@pytest.fixture
def mock_yadisk_client() -> Iterator[MagicMock]:
    with patch("apass.sync.yadisk.yadisk.YaDisk") as mock:
        yield mock.return_value


def test_find_vault_file_exists(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.return_value = MagicMock(resource_id="file123")

    client = YandexDiskClient(mock_token)
    result = client.find_vault_file()

    assert result == "file123"
    mock_yadisk_client.get_meta.assert_called_once_with("/apass/vault.db", fields=["resource_id"])


def test_find_vault_file_not_exists(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.side_effect = PathNotFoundError("Not found")

    client = YandexDiskClient(mock_token)
    result = client.find_vault_file()

    assert result is None


def test_find_vault_file_api_error(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.side_effect = Exception("API error")

    client = YandexDiskClient(mock_token)

    with pytest.raises(CloudApiError, match="Failed to find vault file"):
        client.find_vault_file()


def test_download_vault_file_success(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    def mock_download(path: str, buffer: MagicMock) -> None:
        buffer.write(b"encrypted_vault_data")

    mock_yadisk_client.download.side_effect = mock_download

    client = YandexDiskClient(mock_token)
    result = client.download_vault_file("file123")

    assert result == b"encrypted_vault_data"
    mock_yadisk_client.download.assert_called_once()


def test_download_vault_file_not_found(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.download.side_effect = PathNotFoundError("Not found")

    client = YandexDiskClient(mock_token)

    with pytest.raises(CloudApiError, match="Vault file not found"):
        client.download_vault_file("file123")


def test_download_vault_file_api_error(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.download.side_effect = Exception("API error")

    client = YandexDiskClient(mock_token)

    with pytest.raises(CloudApiError, match="Failed to download vault file"):
        client.download_vault_file("file123")


def test_upload_vault_file_new(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.return_value = MagicMock(resource_id="new_file_id")

    client = YandexDiskClient(mock_token)
    result = client.upload_vault_file(b"encrypted_data")

    assert result == "new_file_id"
    mock_yadisk_client.upload.assert_called_once()
    mock_yadisk_client.get_meta.assert_called_once_with("/apass/vault.db", fields=["resource_id"])


def test_upload_vault_file_overwrite(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.return_value = MagicMock(resource_id="existing_file_id")

    client = YandexDiskClient(mock_token)
    result = client.upload_vault_file(b"encrypted_data", remote_id="existing_file_id")

    assert result == "existing_file_id"
    mock_yadisk_client.upload.assert_called_once()


def test_upload_vault_file_api_error(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.upload.side_effect = Exception("API error")

    client = YandexDiskClient(mock_token)

    with pytest.raises(CloudApiError, match="Failed to upload vault file"):
        client.upload_vault_file(b"encrypted_data")


def test_get_remote_modified_time_success(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.return_value = MagicMock(modified=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc))

    client = YandexDiskClient(mock_token)
    result = client.get_remote_modified_time("file123")

    assert result == "2024-01-15T10:30:00+00:00"
    mock_yadisk_client.get_meta.assert_called_once_with("/apass/vault.db", fields=["modified"])


def test_get_remote_modified_time_not_found(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.side_effect = PathNotFoundError("Not found")

    client = YandexDiskClient(mock_token)
    result = client.get_remote_modified_time("file123")

    assert result is None


def test_get_remote_modified_time_api_error(mock_token: YandexToken, mock_yadisk_client: MagicMock) -> None:
    mock_yadisk_client.get_meta.side_effect = Exception("API error")

    client = YandexDiskClient(mock_token)

    with pytest.raises(CloudApiError, match="Failed to get file metadata"):
        client.get_remote_modified_time("file123")
