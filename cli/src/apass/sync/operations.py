import time
from dataclasses import dataclass

from apass.sync.backend import OAuthProvider, SyncBackend
from apass.sync.oauth import GoogleOAuthProvider
from apass.sync.state import BackendType, load_sync_state, save_sync_state
from apass.sync.yandex_oauth import YandexOAuthProvider
from apass.vault.db import Vault
from apass.vault import keepass
from apass.vault.errors import WrongPasswordError
from apass.vault.merge import MergeResult


class RemoteVaultCorruptedError(Exception):
    pass


class NoRemoteVaultError(Exception):
    pass


class UnsupportedBackendError(Exception):
    pass


_PROVIDERS: dict[BackendType, OAuthProvider] = {
    "gdrive": GoogleOAuthProvider(),
    "yadisk": YandexOAuthProvider(),
}


def perform_sync(
    vault: Vault, master_password: str
) -> SyncResult:
    client = _get_authenticated_client()
    state = load_sync_state()
    merge_result: MergeResult | None = None

    remote_file_id = state.remote_file_id or client.find_vault_file()
    if remote_file_id:
        remote_bytes = client.download_vault_file(remote_file_id)
        merge_result = _perform_merge(vault, remote_bytes, master_password)

    payload = vault.to_bytes(master_password)
    new_file_id = client.upload_vault_file(payload, remote_file_id)

    state.remote_file_id = new_file_id
    state.last_sync_at = int(time.time())
    save_sync_state(state)

    return SyncResult(merge_result=merge_result, remote_file_id=new_file_id)


def compute_diff(vault: Vault, master_password: str) -> MergeResult | None:
    client = _get_authenticated_client()
    state = load_sync_state()

    remote_file_id = state.remote_file_id or client.find_vault_file()
    if not remote_file_id:
        return None
    remote_bytes = client.download_vault_file(remote_file_id)

    return _perform_merge(vault, remote_bytes, master_password, True)


def perform_delete_remote(master_password: str) -> None:
    client = _get_authenticated_client()
    state = load_sync_state()

    remote_file_id = state.remote_file_id or client.find_vault_file()
    if not remote_file_id:
        raise NoRemoteVaultError("No remote vault found")

    remote_bytes = client.download_vault_file(remote_file_id)
    if not keepass.is_valid(remote_bytes, master_password):
        raise RemoteVaultCorruptedError("Wrong password or remote vault is corrupted")

    client.delete_vault_file(remote_file_id)

    state.remote_file_id = None
    state.last_sync_at = None
    save_sync_state(state)


def get_provider() -> OAuthProvider:
    state = load_sync_state()
    return get_provider_for(state.backend)


def get_provider_for(backend: BackendType) -> OAuthProvider:
    try:
        return _PROVIDERS[backend]
    except KeyError as e:
        raise UnsupportedBackendError(f"Unsupported backend: {backend}") from e


def _get_authenticated_client() -> SyncBackend:
    return get_provider().get_authenticated_client()


def _perform_merge(local_vault: Vault, remote_bytes: bytes, master_password: str, dry_run: bool = False) -> MergeResult:
    try:
        return local_vault.merge(master_password, remote_bytes, dry_run)
    except WrongPasswordError:
        raise RemoteVaultCorruptedError("Wrong password or remote vault is corrupted")


@dataclass
class SyncResult:
    merge_result: MergeResult | None
    remote_file_id: str
