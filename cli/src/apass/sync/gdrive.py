import io
from typing import Any

from google.oauth2.credentials import Credentials

VAULT_FILENAME = "apass-vault.db"


class GoogleDriveClient:
    def __init__(self, creds: Credentials) -> None:
        from googleapiclient.discovery import build

        self._service = build("drive", "v3", credentials=creds)

    def find_vault_file(self) -> str | None:
        query = f"name='{VAULT_FILENAME}' and 'appDataFolder' in parents"
        try:
            result = self._service.files().list(q=query, spaces="appDataFolder", fields="files(id)").execute()
        except Exception as e:
            raise DriveApiError(f"Failed to list files: {e}") from e

        files = result.get("files", [])
        if not files:
            return None
        return files[0]["id"]

    def download_vault_file(self, file_id: str) -> bytes:
        try:
            request = self._service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            from googleapiclient.http import MediaIoBaseDownload

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        except Exception as e:
            raise DriveApiError(f"Failed to download vault file: {e}") from e

        return fh.getvalue()

    def upload_vault_file(self, data: bytes, file_id: str | None = None) -> str:
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(data, mimetype="application/octet-stream", resumable=False)

        try:
            if file_id:
                self._service.files().update(fileId=file_id, media_body=media).execute()
                return file_id
            else:
                file_metadata: dict[str, Any] = {
                    "name": VAULT_FILENAME,
                    "parents": ["appDataFolder"],
                }
                result = self._service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                return result["id"]
        except Exception as e:
            raise DriveApiError(f"Failed to upload vault file: {e}") from e

    def get_remote_modified_time(self, file_id: str) -> str | None:
        try:
            result = self._service.files().get(fileId=file_id, fields="modifiedTime").execute()
        except Exception as e:
            raise DriveApiError(f"Failed to get file metadata: {e}") from e
        return result.get("modifiedTime")


class DriveApiError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
