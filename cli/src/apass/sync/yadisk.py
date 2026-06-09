import io

import yadisk
from yadisk.exceptions import PathNotFoundError

from apass.sync.backend import CloudApiError, SyncBackend
from apass.sync.yandex_types import YandexToken

VAULT_PATH = "/apass/vault.db"


class YandexDiskClient(SyncBackend):
    def __init__(self, token: YandexToken) -> None:
        self._token: YandexToken = token
        self._client = yadisk.YaDisk(token=token.access_token)

    def find_vault_file(self) -> str | None:
        try:
            meta = self._client.get_meta(VAULT_PATH, fields=["resource_id"])
            return meta.resource_id
        except PathNotFoundError:
            return None
        except Exception as e:
            raise CloudApiError(f"Failed to find vault file: {e}") from e

    def download_vault_file(self, remote_id: str) -> bytes:
        buffer = io.BytesIO()
        try:
            self._client.download(VAULT_PATH, buffer)
        except PathNotFoundError:
            raise CloudApiError("Vault file not found on Yandex Disk")
        except Exception as e:
            raise CloudApiError(f"Failed to download vault file: {e}") from e
        return buffer.getvalue()

    def upload_vault_file(self, data: bytes, remote_id: str | None = None) -> str:
        # Yandex Disk is path-based: remote_id is ignored by design
        buffer = io.BytesIO(data)
        try:
            self._client.upload(buffer, VAULT_PATH, overwrite=True)
        except Exception as e:
            raise CloudApiError(f"Failed to upload vault file: {e}") from e

        meta = self._client.get_meta(VAULT_PATH, fields=["resource_id"])
        if meta.resource_id is None:
            raise CloudApiError("Failed to get resource_id after upload")
        return meta.resource_id

    def get_remote_modified_time(self, remote_id: str) -> str | None:
        try:
            meta = self._client.get_meta(VAULT_PATH, fields=["modified"])
            if meta.modified is None:
                return None
            return meta.modified.isoformat()
        except PathNotFoundError:
            return None
        except Exception as e:
            raise CloudApiError(f"Failed to get file metadata: {e}") from e
