import io
from typing import Any

from google.oauth2.credentials import Credentials

from apass.sync.backend import CloudApiError, SyncBackend

VAULT_FILENAME = "apass-vault.db"


class GoogleDriveClient(SyncBackend):
    def __init__(self, creds: Credentials) -> None:
        from googleapiclient.discovery import build

        self._service = build("drive", "v3", credentials=creds)

    def find_vault_file(self) -> str | None:
        query = f"name='{VAULT_FILENAME}' and 'appDataFolder' in parents"
        try:
            result = self._service.files().list(q=query, spaces="appDataFolder", fields="files(id)").execute()
        except Exception as e:
            raise CloudApiError(f"Failed to list files: {e}") from e

        files = result.get("files", [])
        if not files:
            return None
        return files[0]["id"]

    def download_vault_file(self, remote_id: str) -> bytes:
        try:
            request = self._service.files().get_media(fileId=remote_id)
            fh = io.BytesIO()
            from googleapiclient.http import MediaIoBaseDownload

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        except Exception as e:
            raise CloudApiError(f"Failed to download vault file: {e}") from e

        return fh.getvalue()

    def upload_vault_file(self, data: bytes, remote_id: str | None = None) -> str:
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(data, mimetype="application/octet-stream", resumable=False)

        try:
            if remote_id:
                self._service.files().update(fileId=remote_id, media_body=media).execute()
                return remote_id
            else:
                file_metadata: dict[str, Any] = {
                    "name": VAULT_FILENAME,
                    "parents": ["appDataFolder"],
                }
                result = self._service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                return result["id"]
        except Exception as e:
            raise CloudApiError(f"Failed to upload vault file: {e}") from e

    def get_remote_modified_time(self, remote_id: str) -> str | None:
        try:
            result = self._service.files().get(fileId=remote_id, fields="modifiedTime").execute()
        except Exception as e:
            raise CloudApiError(f"Failed to get file metadata: {e}") from e
        return result.get("modifiedTime")
