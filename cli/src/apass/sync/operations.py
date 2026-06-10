import time
from dataclasses import dataclass

from apass.crypto import DecryptionError, VaultStructureError, decrypt, encrypt
from apass.sync.backend import OAuthProvider, SyncBackend
from apass.sync.merge import MergeResult, merge_dbs
from apass.sync.oauth import GoogleOAuthProvider
from apass.sync.state import BackendType, load_sync_state, save_sync_state
from apass.sync.yandex_oauth import YandexOAuthProvider
from apass.vault import PasswordDB, Vault, VaultNotInitializedError

_PROVIDERS: dict[BackendType, OAuthProvider] = {
    "gdrive": GoogleOAuthProvider(),
    "yadisk": YandexOAuthProvider(),
}


def perform_push(vault: Vault, master_password: str) -> PushResult:
    client = _get_authenticated_client()
    state = load_sync_state()

    local_db = vault.read_db(master_password)

    remote_file_id = state.remote_file_id
    if not remote_file_id:
        remote_file_id = client.find_vault_file()

    merge_result = None
    if remote_file_id:
        remote_bytes = client.download_vault_file(remote_file_id)
        remote_db = _decrypt_remote_vault(remote_bytes, master_password)
        merge_result = merge_dbs(local_db, remote_db, prefer="local")
        local_db = merge_result.merged_db
        vault.store_db(local_db, master_password)

    payload = _encrypt_vault(local_db, master_password)
    new_file_id = client.upload_vault_file(payload, remote_file_id)

    state.remote_file_id = new_file_id
    state.last_sync_at = int(time.time())
    save_sync_state(state)

    return PushResult(merge_result=merge_result, remote_file_id=new_file_id)


def perform_pull(vault: Vault, master_password: str) -> MergeResult:
    client = _get_authenticated_client()

    remote_file_id = client.find_vault_file()
    if not remote_file_id:
        raise NoRemoteVaultError("No remote vault found")

    remote_bytes = client.download_vault_file(remote_file_id)

    try:
        local_db = vault.read_db(master_password)
    except VaultNotInitializedError:
        local_db = PasswordDB()

    remote_db = _decrypt_remote_vault(remote_bytes, master_password)
    result = merge_dbs(local_db, remote_db, prefer="remote")
    vault.store_db(result.merged_db, master_password)

    state = load_sync_state()
    state.remote_file_id = remote_file_id
    state.last_sync_at = int(time.time())
    save_sync_state(state)

    return result


def compute_diff(vault: Vault, master_password: str) -> MergeResult | None:
    client = _get_authenticated_client()

    remote_file_id = client.find_vault_file()
    if not remote_file_id:
        return None

    remote_bytes = client.download_vault_file(remote_file_id)

    try:
        local_db = vault.read_db(master_password)
    except VaultNotInitializedError:
        local_db = PasswordDB()

    remote_db = _decrypt_remote_vault(remote_bytes, master_password)
    return merge_dbs(local_db, remote_db, prefer="local")


def perform_delete_remote(master_password: str) -> None:
    client = _get_authenticated_client()
    state = load_sync_state()

    remote_file_id = state.remote_file_id or client.find_vault_file()
    if not remote_file_id:
        raise NoRemoteVaultError("No remote vault found")

    remote_bytes = client.download_vault_file(remote_file_id)
    _decrypt_remote_vault(remote_bytes, master_password)

    client.delete_vault_file(remote_file_id)

    state.remote_file_id = None
    state.last_sync_at = None
    save_sync_state(state)


def get_provider() -> OAuthProvider:
    state = load_sync_state()
    provider = _PROVIDERS.get(state.backend)
    if not provider:
        raise UnsupportedBackendError(f"Unsupported backend: {state.backend}")
    return provider


def _get_authenticated_client() -> SyncBackend:
    return get_provider().get_authenticated_client()


def _decrypt_remote_vault(remote_bytes: bytes, master_password: str) -> PasswordDB:
    try:
        remote_plaintext = decrypt(remote_bytes, master_password)
    except VaultStructureError:
        raise RemoteVaultCorruptedError("Remote vault is corrupted")
    except DecryptionError:
        raise RemoteVaultCorruptedError("Wrong password or remote vault is corrupted")

    return PasswordDB.deserialize(remote_plaintext)


def _encrypt_vault(db: PasswordDB, master_password: str) -> bytes:
    plaintext = db.serialize()
    return encrypt(plaintext, master_password)


@dataclass
class PushResult:
    merge_result: MergeResult | None
    remote_file_id: str


class RemoteVaultCorruptedError(Exception):
    pass


class NoRemoteVaultError(Exception):
    pass


class UnsupportedBackendError(Exception):
    pass
