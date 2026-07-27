from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import cast

from pykeepass import PyKeePass, create_database
from pykeepass.entry import Entry

from apass.vault import keepass, merge
from apass.vault.errors import (
    EntryAlreadyExistsError,
    EntryNotFoundError,
    VaultNotInitializedError,
)
from apass.vault.merge import MergeResult


@dataclass
class PasswordEntry:
    name: str
    password: str
    login: str
    notes: str = ""

    @classmethod
    def from_pykeepass(cls, entry: Entry) -> PasswordEntry:
        return cls(
            name=cast(str, entry.title),
            password=cast(str, entry.password),
            login=entry.username if entry.username else "",
            notes=entry.notes if entry.notes else "",
        )

    def __str__(self) -> str:
        return self.name + (f"/{self.login}" if self.login else "")


class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    @property
    def vault_file(self) -> Path:
        return self._vault_file

    def init_db(self, master_password: str) -> None:
        create_database(self._vault_file, password=master_password)

    def save(
        self,
        name: str,
        login: str,
        password: str,
        master_password: str,
        force: bool = False,
        notes: str | None = None,
    ) -> None:
        kp = self._load(master_password)
        existing = keepass.find_alive(kp, name, login)
        if existing is not None:
            if not force:
                raise EntryAlreadyExistsError(name)
            existing.password = password
            existing.username = login
            if notes is not None:
                existing.notes = notes
            existing.touch(modify=True)
        else:
            kp.add_entry(
                kp.root_group,
                name,
                login,
                password,
                notes=notes,
            )
        self._save(kp)

    def search(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp = self._load(master_password)
        return [PasswordEntry.from_pykeepass(e) for e in keepass.find_all_alive(kp) if keepass.matches(e, query)]

    def remove(self, name: str, login: str, master_password: str) -> None:
        kp = self._load(master_password)
        entry = keepass.find_alive(kp, name, login)
        if entry is None:
            raise EntryNotFoundError(name)
        entry.touch(modify=True)
        kp.trash_entry(entry)
        self._save(kp)

    def restore(self, name: str, login: str, master_password: str) -> None:
        kp = self._load(master_password)
        entry = keepass.find_trashed(kp, name, login)
        if entry is None:
            raise EntryNotFoundError(name)
        kp.move_entry(entry, kp.root_group)
        entry.touch(modify=True)
        self._save(kp)

    def list_trashed(self, query: str, master_password: str) -> list[PasswordEntry]:
        kp = self._load(master_password)
        return [PasswordEntry.from_pykeepass(e) for e in keepass.find_all_trashed(kp) if keepass.matches(e, query)]

    def to_bytes(self, master_password: str) -> bytes:
        buf = BytesIO()
        self._load(master_password).save(buf)
        return buf.getvalue()

    def merge(
        self, master_password: str, remote_vault_bytes: bytes, dry_run: bool = False
    ) -> MergeResult:
        local = self._load(master_password)
        remote = keepass.from_bytes(remote_vault_bytes, master_password)
        result = merge.merge_dbs(local, remote, dry_run=dry_run)
        if not dry_run:
            self._save(local)
        return result

    def _load(self, master_password: str) -> PyKeePass:
        try:
            data = self._vault_file.read_bytes()
        except FileNotFoundError as e:
            raise VaultNotInitializedError() from e
        return keepass.from_bytes(data, master_password)

    def _save(self, kp: PyKeePass) -> None:
        kp.save(self._vault_file)
