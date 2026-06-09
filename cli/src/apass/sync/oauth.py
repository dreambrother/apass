import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from apass._atomic_write import atomic_write_bytes
from apass.config import get_db_path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
USERINFO_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
OPENID_SCOPE = "openid"
SCOPES = [DRIVE_APPDATA_SCOPE, USERINFO_SCOPE, OPENID_SCOPE]


@dataclass
class OAuthConfig:
    client_id: str
    client_secret: str


def get_oauth_config_path() -> Path:
    return get_db_path().parent / "gdrive_oauth.json"


def get_token_path() -> Path:
    return get_db_path().parent / "gdrive_token.json"


def load_oauth_config() -> OAuthConfig | None:
    path = get_oauth_config_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return OAuthConfig(
        client_id=data["client_id"],
        client_secret=data["client_secret"],
    )


def save_oauth_config(config: OAuthConfig) -> None:
    path = get_oauth_config_path()
    data = {"client_id": config.client_id, "client_secret": config.client_secret}
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, plaintext)


def load_credentials() -> Credentials | None:
    path = get_token_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return Credentials.from_authorized_user_info(data, scopes=SCOPES)


def save_credentials(creds: Credentials) -> None:
    path = get_token_path()
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, plaintext)


def delete_credentials() -> None:
    path = get_token_path()
    if path.exists():
        path.unlink()


def refresh_credentials(creds: Credentials) -> Credentials:
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds


def run_login_flow(config: OAuthConfig) -> Credentials:
    client_config = {
        "installed": {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uris": ["http://127.0.0.1"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = cast(Credentials, flow.run_local_server(port=0, open_browser=True))
    save_credentials(creds)
    return creds


def get_user_email(creds: Credentials) -> str:
    import google.auth.transport.requests
    import requests

    if creds.expired:
        creds.refresh(google.auth.transport.requests.Request())

    response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    response.raise_for_status()
    return response.json()["email"]
