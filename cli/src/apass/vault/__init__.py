from dataclasses import dataclass
import io
from pathlib import Path
from typing import cast

from pykeepass import Group, PyKeePass, create_database
from pykeepass.entry import Entry
from pykeepass.exceptions import (
    CredentialsError,
    HeaderChecksumError,
    PayloadChecksumError,
)

import apass.vault.keepass as keepass
from apass.vault import merge
from apass.vault.errors import (
    CorruptedVaultError,
    EntryAlreadyExistsError,
    EntryNotFoundError,
    VaultNotInitializedError,
    WrongPasswordError,
)
from apass.vault.merge import MergeResult


@dataclass
class PasswordEntry:
    name: str
    password: str
    login: str | None = None

class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    def init_db(self, master_password: str) -> None:
        create_database(self._vault_file, password=master_password)

    def save(
        self,
        service_name: str,
        service_password: str,
        master_password: str,
        service_login: str | None = None,
        force: bool = False,
    ) -> None:
        kp = self._load(master_password)
        existing = keepass.find_alive(kp, service_name)
        login = service_login if service_login is not None else ""
        if existing is not None:
            if not force:
                raise EntryAlreadyExistsError(service_name)
            existing.password = service_password
            if service_login is not None:
                existing.username = login
            existing.touch(modify=True)
        else:
            entry = kp.add_entry(
                kp.root_group,
                service_name,
                login,
                service_password,
            )
            entry.touch(modify=True)
        self._save(kp)

    def search(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp = self._load(master_password)
        return [Vault._to_view(e) for e in keepass.find_all_alive(kp) if self._matches(e, query)]

    def remove(self, name: str, master_password: str) -> None:
        kp = self._load(master_password)
        entry = keepass.find_alive(kp, name)
        if entry is None:
            raise EntryNotFoundError(name)
        entry.touch(modify=True)
        kp.trash_entry(entry)
        self._save(kp)

    def restore(self, name: str, master_password: str) -> None:
        kp = self._load(master_password)
        entry = keepass.find_trashed(kp, name)
        if entry is None:
            raise EntryNotFoundError(name)
        kp.move_entry(entry, kp.root_group)
        entry.touch(modify=True)
        self._save(kp)

    def list_trashed(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp = self._load(master_password)
        recycle = cast(Group, kp.recyclebin_group)
        if recycle is None:
            return []
        return [Vault._to_view(e) for e in recycle.entries if self._matches(e, query)]

    def to_bytes(self, master_password: str) -> bytes:
        buf = io.BytesIO()
        self._load(master_password).save(buf)
        return buf.getvalue()

    def merge(
        self, master_password: str, remote_vault_bytes: bytes, dry_run: bool = False
    ) -> MergeResult:
        local = self._load(master_password)
        remote = Vault._from_bytes(remote_vault_bytes, master_password)
        result = merge.merge_dbs(local, remote, dry_run=dry_run)
        if not dry_run:
            self._save(local)
        return result

    def _load(self, master_password: str) -> PyKeePass:
        if not self._vault_file.exists():
            raise VaultNotInitializedError()
        with open(self._vault_file, "rb") as f:
            return Vault._from_bytes(f.read(), master_password)

    def _save(self, kp: PyKeePass) -> None:
        kp.save(self._vault_file)

    @staticmethod
    def is_valid(db_bytes: bytes, master_password: str) -> bool:
        try:
            _ = Vault._from_bytes(db_bytes, master_password)
            return True
        except (WrongPasswordError, CorruptedVaultError):
            return False

    @staticmethod
    def _from_bytes(db_bytes: bytes, master_password: str) -> PyKeePass:
        try:
            kp = PyKeePass(io.BytesIO(db_bytes), password=master_password)
        except CredentialsError as e:
            raise WrongPasswordError() from e
        except (HeaderChecksumError, PayloadChecksumError) as e:
            raise CorruptedVaultError() from e
        except Exception as e:
            raise CorruptedVaultError() from e
        keepass.validate_entries(kp)
        return kp

    @staticmethod
    def _matches(entry: Entry, query: str) -> bool:
        if entry.title is None:
            return False
        return query.lower() in entry.title.lower()

    @staticmethod
    def _to_view(entry: Entry) -> PasswordEntry:
        return PasswordEntry(
            name=cast(str, entry.title),
            password=cast(str, entry.password),
            login=entry.username,
        )
