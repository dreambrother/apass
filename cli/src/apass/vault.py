import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from apass.crypto import decrypt, encrypt

CURRENT_DB_VERSION: str = "1.0"


class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    def create(
        self, service_name: str, service_password: str, user_password: str
    ) -> None:
        db = self._read_db(user_password)
        if any(service_name == entry.name for entry in db.entries):
            raise EntryAlreadyExistsError(service_name)

        db.entries.append(
            PasswordEntry(service_name, service_password, int(time.time()))
        )
        self._store_db(db, user_password)

    def init_db(self, user_password: str) -> None:
        db = PasswordDB()
        self._store_db(db, user_password)

    def _read_db(self, user_password: str) -> PasswordDB:
        if not self._vault_file.exists():
            return PasswordDB()
        payload = self._vault_file.read_bytes()
        plaintext = decrypt(payload, user_password)
        if plaintext is None:
            raise WrongPasswordError()
        data = json.loads(plaintext)
        return PasswordDB(
            ver=data["ver"],
            entries=[PasswordEntry(**e) for e in data["entries"]],
        )

    def _store_db(self, db: PasswordDB, user_password: str) -> None:
        plaintext = json.dumps(asdict(db), ensure_ascii=False).encode("utf-8")
        payload = encrypt(plaintext, user_password)
        self._vault_file.parent.mkdir(parents=True, exist_ok=True)
        self._vault_file.write_bytes(payload)


@dataclass
class PasswordDB:
    ver: str = CURRENT_DB_VERSION
    entries: list[PasswordEntry] = field(default_factory=list)


@dataclass
class PasswordEntry:
    name: str
    password: str
    modified: int


class EntryAlreadyExistsError(Exception):
    def __init__(self, entry_name: str) -> None:
        self.entry_name = entry_name
        super().__init__(f"Entry for {entry_name!r} already exists")


class WrongPasswordError(Exception):
    def __init__(self) -> None:
        super().__init__("Wrong password or corrupted vault")
