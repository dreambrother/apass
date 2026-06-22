from unittest.mock import MagicMock, patch

import pytest

from apass.sync.yandex_oauth import (
    YandexOAuthConfig,
    YandexToken,
    delete_yandex_token,
    get_yandex_user_email,
    load_yandex_oauth_config,
    load_yandex_token,
    save_yandex_oauth_config,
    save_yandex_token,
)


@pytest.fixture
def temp_config_dir(tmp_path):
    with patch("apass.sync.yandex_oauth.get_db_path") as mock_get_db_path:
        mock_get_db_path.return_value = tmp_path / "vault.db"
        yield tmp_path


def test_save_and_load_oauth_config(temp_config_dir) -> None:
    config = YandexOAuthConfig(client_id="test_client_id", client_secret="test_client_secret")
    save_yandex_oauth_config(config)

    loaded = load_yandex_oauth_config()
    assert loaded is not None
    assert loaded.client_id == "test_client_id"
    assert loaded.client_secret == "test_client_secret"


def test_load_oauth_config_not_exists() -> None:
    result = load_yandex_oauth_config()
    assert result is None


def test_save_and_load_token() -> None:
    token = YandexToken(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_type="bearer",
        expires_in=3600,
    )
    save_yandex_token(token)

    loaded = load_yandex_token()
    assert loaded is not None
    assert loaded.access_token == "test_access_token"
    assert loaded.refresh_token == "test_refresh_token"
    assert loaded.token_type == "bearer"
    assert loaded.expires_in == 3600


def test_load_token_not_exists() -> None:
    result = load_yandex_token()
    assert result is None


def test_delete_token() -> None:
    token = YandexToken(access_token="test_access_token")
    save_yandex_token(token)

    delete_yandex_token()

    result = load_yandex_token()
    assert result is None


def test_delete_token_not_exists() -> None:
    delete_yandex_token()


def test_get_yandex_user_email_with_emails() -> None:
    token = YandexToken(access_token="test_token")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "emails": ["user@example.com", "user2@example.com"],
        "default_email": "default@example.com",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("apass.sync.yandex_oauth.requests.get", return_value=mock_response):
        result = get_yandex_user_email(token)

    assert result == "user@example.com"


def test_get_yandex_user_email_with_default_email() -> None:
    token = YandexToken(access_token="test_token")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "emails": [],
        "default_email": "default@example.com",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("apass.sync.yandex_oauth.requests.get", return_value=mock_response):
        result = get_yandex_user_email(token)

    assert result == "default@example.com"


def test_get_yandex_user_email_unknown() -> None:
    token = YandexToken(access_token="test_token")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "emails": [],
    }
    mock_response.raise_for_status = MagicMock()

    with patch("apass.sync.yandex_oauth.requests.get", return_value=mock_response):
        result = get_yandex_user_email(token)

    assert result == "unknown"
