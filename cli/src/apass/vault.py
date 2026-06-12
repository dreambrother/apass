import base64
import io
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pykeepass import PyKeePass, create_database
from pykeepass.entry import Entry
from pykeepass.exceptions import (
    CredentialsError,
    HeaderChecksumError,
    PayloadChecksumError,
)

CURRENT_DB_VERSION: int = 4


class VaultNotInitializedError(Exception):
    def __init__(self) -> None:
        super().__init__("Vault is not initialized. Run 'apass init' first.")


class EntryAlreadyExistsError(Exception):
    def __init__(self, entry_name: str) -> None:
        super().__init__(f"Entry for {entry_name!r} already exists")


class EntryNotFoundError(Exception):
    def __init__(self, entry_name: str) -> None:
        super().__init__(f"Entry for {entry_name!r} is not found")


class CorruptedVaultError(Exception):
    def __init__(self) -> None:
        super().__init__("Vault file is corrupted or has an unsupported format")


class WrongPasswordError(Exception):
    def __init__(self) -> None:
        super().__init__("Wrong password or corrupted vault")


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
        existing = self._find_alive(kp, service_name)
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
        kp.save()

    def search(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp: Any = self._load(master_password)
        return [
            Vault._to_entry(e)
            for e in kp.entries
            if not self._is_trashed(kp, e) and self._matches(e, query)
        ]

    def read_db(self, master_password: str) -> PasswordDB:
        kp: Any = self._load(master_password)
        entries = [Vault._to_entry(e) for e in kp.entries if not self._is_trashed(kp, e)]
        trashed = [Vault._to_entry(e) for e in kp.entries if self._is_trashed(kp, e)]
        return PasswordDB(ver=CURRENT_DB_VERSION, entries=entries, trashed=trashed)

    def store_db(self, db: PasswordDB, master_password: str) -> None:
        kp: Any = self._load(master_password)
        for e in list(kp.entries):
            kp.delete_entry(e)
        for entry in db.entries:
            kp_entry = kp.add_entry(
                kp.root_group,
                entry.name,
                entry.login or "",
                entry.password,
            )
            Vault._set_entry_uuid(kp_entry, entry.uuid)
            Vault._set_entry_mtime(kp_entry, entry.modified)
        for entry in db.trashed:
            kp_entry = kp.add_entry(
                kp.root_group,
                entry.name,
                entry.login or "",
                entry.password,
            )
            Vault._set_entry_uuid(kp_entry, entry.uuid)
            Vault._set_entry_mtime(kp_entry, entry.modified)
            kp.trash_entry(kp_entry)
        kp.save()

    def remove(self, name: str, master_password: str) -> None:
        kp: Any = self._load(master_password)
        entry = self._find_alive(kp, name)
        if entry is None:
            raise EntryNotFoundError(name)
        entry.touch(modify=True)
        kp.trash_entry(entry)
        kp.save()

    def restore(self, name: str, master_password: str) -> None:
        kp: Any = self._load(master_password)
        entry = self._find_trashed(kp, name)
        if entry is None:
            raise EntryNotFoundError(name)
        kp.move_entry(entry, kp.root_group)
        entry.touch(modify=True)
        kp.save()

    def list_trashed(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp: Any = self._load(master_password)
        recycle = kp.recyclebin_group
        if recycle is None:
            return []
        return [
            Vault._to_entry(e)
            for e in recycle.entries
            if e.title and query.lower() in e.title.lower()
        ]

    @staticmethod
    def read_db_from_bytes(data: bytes, master_password: str) -> PasswordDB:
        try:
            kp: Any = PyKeePass(io.BytesIO(data), password=master_password)
        except CredentialsError as e:
            raise WrongPasswordError() from e
        except (HeaderChecksumError, PayloadChecksumError) as e:
            raise CorruptedVaultError() from e
        except Exception as e:
            raise CorruptedVaultError() from e

        def is_trashed(entry: Entry) -> bool:
            recycle = kp.recyclebin_group
            return recycle is not None and entry in recycle.entries

        entries = [Vault._to_entry(e) for e in kp.entries if not is_trashed(e)]
        trashed = [Vault._to_entry(e) for e in kp.entries if is_trashed(e)]
        return PasswordDB(ver=CURRENT_DB_VERSION, entries=entries, trashed=trashed)

    @staticmethod
    def write_db_to_bytes(db: PasswordDB, master_password: str) -> bytes:
        buf = io.BytesIO()
        with tempfile.NamedTemporaryFile(suffix=".kdbx") as tmp:
            kp: Any = create_database(Path(tmp.name), password=master_password)
            for entry in db.entries:
                kp_entry = kp.add_entry(
                    kp.root_group,
                    entry.name,
                    entry.login or "",
                    entry.password,
                )
                Vault._set_entry_uuid(kp_entry, entry.uuid)
                Vault._set_entry_mtime(kp_entry, entry.modified)
            for entry in db.trashed:
                kp_entry = kp.add_entry(
                    kp.root_group,
                    entry.name,
                    entry.login or "",
                    entry.password,
                )
                Vault._set_entry_uuid(kp_entry, entry.uuid)
                Vault._set_entry_mtime(kp_entry, entry.modified)
                kp.trash_entry(kp_entry)
            kp.save(buf)
        return buf.getvalue()

    @staticmethod
    def _set_entry_uuid(kp_entry: Entry, target_uuid: UUID) -> None:
        kp_entry._element.find('UUID').text = base64.b64encode(target_uuid.bytes).decode('utf-8')

    @staticmethod
    def _set_entry_mtime(kp_entry: Entry, modified: int) -> None:
        kp_entry.mtime = datetime.fromtimestamp(modified, tz=timezone.utc)

    def _load(self, master_password: str) -> Any:
        if not self._vault_file.exists():
            raise VaultNotInitializedError()
        try:
            return PyKeePass(str(self._vault_file), password=master_password)
        except CredentialsError as e:
            raise WrongPasswordError() from e
        except (HeaderChecksumError, PayloadChecksumError) as e:
            raise CorruptedVaultError() from e
        except Exception as e:
            raise CorruptedVaultError() from e

    def _is_trashed(self, kp: Any, entry: Entry) -> bool:
        recycle = kp.recyclebin_group
        return recycle is not None and entry in recycle.entries

    def _find_alive(self, kp: Any, name: str) -> Entry | None:
        for e in kp.entries:
            if e.title == name and not self._is_trashed(kp, e):
                return e
        return None

    def _find_trashed(self, kp: Any, name: str) -> Entry | None:
        for e in kp.entries:
            if e.title == name and self._is_trashed(kp, e):
                return e
        return None

    def _matches(self, entry: Entry, query: str) -> bool:
        if entry.title is None:
            return False
        return query.lower() in entry.title.lower()

    @staticmethod
    def _to_entry(kp_entry: Entry) -> PasswordEntry:
        mtime = kp_entry.mtime
        modified = int(mtime.timestamp()) if mtime is not None else 0
        return PasswordEntry(
            uuid=kp_entry.uuid,
            name=kp_entry.title or "",
            login=kp_entry.username,
            password=kp_entry.password or "",
            modified=modified,
        )


@dataclass
class PasswordDB:
    ver: int = CURRENT_DB_VERSION
    entries: list[PasswordEntry] = field(default_factory=list)
    trashed: list[PasswordEntry] = field(default_factory=list)


@dataclass
class PasswordEntry:
    uuid: UUID
    name: str
    login: str | None
    password: str
    modified: int  # Unix timestamp (UTC)
