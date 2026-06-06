import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from apass.crypto import DecryptionError, VaultStructureError, decrypt, encrypt

CURRENT_DB_VERSION: int = 1


class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    def init_db(self, master_password: str) -> None:
        db = PasswordDB()
        self._store_db(db, master_password)

    def save(self, service_name: str, service_password: str, master_password: str, force: bool = False) -> None:
        db = self._read_db(master_password)
        for entry in db.entries:
            if entry.name == service_name:
                if not force:
                    raise EntryAlreadyExistsError(service_name)
                entry.password = service_password
                break
        else:
            db.entries.append(
                PasswordEntry(
                    self._new_id(db),
                    service_name,
                    service_password,
                    int(datetime.now(timezone.utc).timestamp()),
                )
            )
        self._store_db(db, master_password)

    def _new_id(self, db: PasswordDB) -> int:
        return max((entry.id for entry in db.entries), default=0) + 1

    def search(self, query: str, master_password: str) -> list[PasswordEntry]:
        db = self._read_db(master_password)
        return [entry for entry in db.entries if query.lower() in entry.name.lower()]

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

        data = json.loads(plaintext)
        found_ver = data.get("ver")
        if not isinstance(found_ver, int) or found_ver != CURRENT_DB_VERSION:
            raise UnsupportedDBVersionError(found_ver)

        return PasswordDB(
            ver=data["ver"],
            entries=[PasswordEntry(**e) for e in data["entries"]],
        )

    def _store_db(self, db: PasswordDB, master_password: str) -> None:
        plaintext = json.dumps(asdict(db), ensure_ascii=False).encode("utf-8")
        payload = encrypt(plaintext, master_password)

        self._vault_file.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to a temporary file on the same volume,
        # fsync, then rename over the real path.
        fd, tmp_path = tempfile.mkstemp(
            dir=self._vault_file.parent,
            prefix="." + self._vault_file.name + ".",
            suffix=".tmp",
        )
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)

        # Restrict permissions: owner-only read+write.
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self._vault_file)


@dataclass
class PasswordDB:
    ver: int = CURRENT_DB_VERSION
    entries: list[PasswordEntry] = field(default_factory=list)


@dataclass
class PasswordEntry:
    id: int
    name: str
    password: str
    modified: int  # Unix timestamp (UTC)


class VaultNotInitializedError(Exception):
    def __init__(self) -> None:
        super().__init__("Vault is not initialized. Run 'apass init' first.")


class EntryAlreadyExistsError(Exception):
    def __init__(self, entry_name: str) -> None:
        self.entry_name = entry_name
        super().__init__(f"Entry for {entry_name!r} already exists")


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
