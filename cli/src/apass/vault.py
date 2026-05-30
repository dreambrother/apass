import time
from dataclasses import dataclass, field
from pathlib import Path

CURRENT_DB_VERSION: str = "1.0"


class Vault:
    def __init__(self, vault_file: Path) -> None:
        self._vault_file = vault_file

    def create(
        self, service_name: str, service_password: str, user_password: str
    ) -> None:
        db = self._read_db(user_password)
        if any(service_name == entry.name for entry in db.entries):
            raise EnvironmentError(f"Entry for {service_name} already exists")

        db.entries.append(
            PasswordEntry(service_name, service_password, int(time.time()))
        )
        self._store_db(db, user_password)

    def init_db(self, user_password: str) -> None:
        db = PasswordDB()
        self._store_db(db, user_password)

    def _read_db(self, user_password: str) -> PasswordDB:
        return PasswordDB()

    def _store_db(self, db: PasswordDB, user_password: str) -> None:
        pass


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
    pass
