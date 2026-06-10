import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from apass._atomic_write import atomic_write_bytes
from apass.config import get_db_path
from apass.sync.backend import SyncBackend
from apass.sync.yandex_types import YandexToken

YANDEX_OAUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USERINFO_URL = "https://login.yandex.ru/info"

SCOPES = ["cloud_api:disk.read", "cloud_api:disk.write"]
REDIRECT_PORT = 9000
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}"


class YandexOAuthError(Exception):
    pass


@dataclass
class YandexOAuthConfig:
    client_id: str
    client_secret: str


def get_yandex_oauth_config_path() -> Path:
    return get_db_path().parent / "yadisk_oauth.json"


def get_yandex_token_path() -> Path:
    return get_db_path().parent / "yadisk_token.json"


def load_yandex_oauth_config() -> YandexOAuthConfig | None:
    path = get_yandex_oauth_config_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return YandexOAuthConfig(
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )


def save_yandex_oauth_config(config: YandexOAuthConfig) -> None:
    path = get_yandex_oauth_config_path()
    data = {"client_id": config.client_id, "client_secret": config.client_secret}
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, plaintext)


def load_yandex_token() -> YandexToken | None:
    path = get_yandex_token_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return YandexToken(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_type=data.get("token_type", "bearer"),
        expires_in=data.get("expires_in"),
    )


def save_yandex_token(token: YandexToken) -> None:
    path = get_yandex_token_path()
    data = {
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
    }
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, plaintext)


def delete_yandex_token() -> None:
    path = get_yandex_token_path()
    if path.exists():
        path.unlink()


def run_yandex_login_flow(config: YandexOAuthConfig) -> YandexToken:
    import http.server
    import socketserver
    import threading
    import time as time_module
    import urllib.parse
    import webbrowser

    auth_code_holder: list[str | None] = [None]
    auth_code_event = threading.Event()

    class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            code = params.get("code", [None])[0]
            if code:
                auth_code_holder[0] = code
                auth_code_event.set()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if code:
                self.wfile.write(b"<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>")
            else:
                self.wfile.write(b"")

        def log_message(self, format: str, *args: object) -> None:
            pass

    with socketserver.TCPServer(("127.0.0.1", REDIRECT_PORT), OAuthCallbackHandler) as httpd:
        auth_url = (
            f"{YANDEX_OAUTH_URL}"
            f"?response_type=code"
            f"&client_id={config.client_id}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            f"&scope={urllib.parse.quote(' '.join(SCOPES))}"
        )

        print(f"Please open this URL to authorize: {auth_url}")
        webbrowser.open(auth_url)

        httpd.timeout = 1.0
        start_time = time_module.time()
        while not auth_code_event.is_set() and time_module.time() - start_time < 300:
            httpd.handle_request()

    auth_code = auth_code_holder[0]
    if auth_code is None:
        raise YandexOAuthError("Failed to receive authorization code")

    token_data = _exchange_code_for_token(config, auth_code)
    token = YandexToken(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type", "bearer"),
        expires_in=token_data.get("expires_in"),
    )
    save_yandex_token(token)
    return token


def _exchange_code_for_token(config: YandexOAuthConfig, code: str) -> dict[str, Any]:
    response = requests.post(
        YANDEX_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
    )
    response.raise_for_status()
    return response.json()


def refresh_yandex_token(config: YandexOAuthConfig) -> YandexToken:
    token = load_yandex_token()
    if not token or not token.refresh_token:
        raise YandexOAuthError("No refresh token available. Run 'apass sync login' again.")

    response = requests.post(
        YANDEX_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
    )
    response.raise_for_status()
    data = response.json()

    new_token = YandexToken(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", token.refresh_token),
        token_type=data.get("token_type", "bearer"),
        expires_in=data.get("expires_in"),
    )
    save_yandex_token(new_token)
    return new_token


def get_yandex_user_email(token: YandexToken) -> str:
    response = requests.get(
        YANDEX_USERINFO_URL,
        headers={"Authorization": f"OAuth {token.access_token}"},
        params={"format": "json"},
    )
    response.raise_for_status()
    data = response.json()
    emails = data.get("emails", [])
    if emails:
        return emails[0]
    return data.get("default_email", "unknown")




class YandexOAuthProvider:
    def load_config(self) -> bool:
        return load_yandex_oauth_config() is not None

    def save_config(self, client_id: str, client_secret: str) -> None:
        config = YandexOAuthConfig(client_id=client_id, client_secret=client_secret)
        save_yandex_oauth_config(config)

    def run_login_flow(self) -> str:
        config = load_yandex_oauth_config()
        if not config:
            raise RuntimeError("OAuth not configured")
        token = run_yandex_login_flow(config)
        return get_yandex_user_email(token)

    def is_logged_in(self) -> bool:
        return load_yandex_token() is not None

    def delete_credentials(self) -> None:
        delete_yandex_token()

    def get_display_name(self) -> str:
        return "Yandex Disk"

    def get_authenticated_client(self) -> SyncBackend:
        from apass.sync.backend import NotLoggedInError
        from apass.sync.yadisk import YandexDiskClient

        token = load_yandex_token()
        if not token:
            raise NotLoggedInError()
        config = load_yandex_oauth_config()
        if not config:
            raise NotLoggedInError()
        try:
            token = refresh_yandex_token(config)
        except Exception:
            raise NotLoggedInError()
        return YandexDiskClient(token)
