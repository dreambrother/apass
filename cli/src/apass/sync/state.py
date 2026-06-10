import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from apass._atomic_write import atomic_write_bytes
from apass.config import get_db_path

BackendType = Literal["gdrive", "yadisk"]


@dataclass
class SyncState:
    remote_file_id: str | None = None
    account_email: str | None = None
    last_sync_at: int | None = None
    backend: BackendType = "gdrive"

    def is_configured(self) -> bool:
        return self.remote_file_id is not None


def get_sync_state_path() -> Path:
    return get_db_path().parent / "sync.json"


def load_sync_state() -> SyncState:
    path = get_sync_state_path()
    if not path.exists():
        return SyncState()
    data = json.loads(path.read_text())
    return SyncState(
        remote_file_id=data.get("remote_file_id"),
        account_email=data.get("account_email"),
        last_sync_at=data.get("last_sync_at"),
        backend=data.get("backend", "gdrive"),
    )


def save_sync_state(state: SyncState) -> None:
    path = get_sync_state_path()
    data = asdict(state)
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, plaintext)
