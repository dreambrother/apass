import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from apass._atomic_write import atomic_write_bytes
from apass.crypto import DecryptionError, VaultStructureError, decrypt, encrypt

CURRENT_DB_VERSION: int = 1


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


class UnsupportedDBVersionError(Exception):
    def __init__(self, found_version: int) -> None:
        self.found_version = found_version
        super().__init__(
            f"Unsupported vault version {found_version}. "
            f"Expected {CURRENT_DB_VERSION}. Please upgrade apass."
        )


class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    def init_db(self, master_password: str) -> None:
        db = PasswordDB()
        self._store_db(db, master_password)

    def save(
        self,
        service_name: str,
        service_password: str,
        master_password: str,
        service_login: str | None = None,
        force: bool = False
    ) -> None:
        db = self._read_db(master_password)
        for entry in db.entries:
            if entry.name == service_name:
                if not force:
                    raise EntryAlreadyExistsError(service_name)
                if service_login is not None:
                    entry.login = service_login
                entry.password = service_password
                entry.modified = int(datetime.now(timezone.utc).timestamp())
                break
        else:
            db.entries.append(
                PasswordEntry(
                    service_name,
                    service_login,
                    service_password,
                    int(datetime.now(timezone.utc).timestamp()),
                )
            )
        self._store_db(db, master_password)

    def search(self, query: str, master_password: str) -> list[PasswordEntry]:
        db = self._read_db(master_password)
        return [entry for entry in db.entries if query.lower() in entry.name.lower()]

    def read_db(self, master_password: str) -> PasswordDB:
        return self._read_db(master_password)

    def store_db(self, db: PasswordDB, master_password: str) -> None:
        self._store_db(db, master_password)

    def remove(self, name: str, master_password: str) -> None:
        db = self._read_db(master_password)
        found = next((e for e in db.entries if e.name == name), None)
        if found is None:
            raise EntryNotFoundError(name)

        db.entries.remove(found)
        db.tombstones.append(Tombstone(name, int(datetime.now(timezone.utc).timestamp())))
        self._store_db(db, master_password)

    def _read_db(self, master_password: str) -> PasswordDB:
        if not self._vault_file.exists():
            raise VaultNotInitializedError()

        payload = self._vault_file.read_bytes()
        try:
            plaintext = decrypt(payload, master_password)
        except VaultStructureError:
            raise CorruptedVaultError() from None
        except DecryptionError:
            raise WrongPasswordError() from None

        return PasswordDB.deserialize(plaintext)

    def _store_db(self, db: PasswordDB, master_password: str) -> None:
        plaintext = db.serialize()
        payload = encrypt(plaintext, master_password)
        atomic_write_bytes(self._vault_file, payload)


@dataclass
class PasswordDB:
    ver: int = CURRENT_DB_VERSION
    entries: list[PasswordEntry] = field(default_factory=list)
    tombstones: list[Tombstone] = field(default_factory=list)

    def serialize(self) -> bytes:
        return json.dumps(asdict(self), ensure_ascii=False).encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> PasswordDB:
        parsed = json.loads(data)
        found_ver = parsed.get("ver")
        if found_ver != CURRENT_DB_VERSION:
            raise UnsupportedDBVersionError(found_ver)
        entries = [
            PasswordEntry(
                e["name"],
                e.get("login"),
                e["password"],
                e["modified"]
            )
            for e in parsed["entries"]
        ]
        tombstones = [
            Tombstone(t["name"], t["modified"]) for t in parsed["tombstones"]
        ]
        return cls(ver=found_ver, entries=entries, tombstones=tombstones)


@dataclass
class PasswordEntry:
    name: str
    login: str | None
    password: str
    modified: int  # Unix timestamp (UTC)


@dataclass
class Tombstone:
    name: str
    modified: int  # Unix timestamp (UTC); when the delete happened
