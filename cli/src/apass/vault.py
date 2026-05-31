import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from apass.crypto import decrypt, encrypt

CURRENT_DB_VERSION: str = "1.0"

# Safety limit: reject payloads larger than this before even attempting
# decryption, and reject plaintext larger than this after decryption.
_MAX_PAYLOAD_BYTES = 100 * 1024 * 1024   # 100 MiB
_MAX_PLAINTEXT_BYTES = 10 * 1024 * 1024  # 10 MiB


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
            PasswordEntry(
                service_name,
                service_password,
                int(datetime.now(timezone.utc).timestamp()),
            )
        )
        self._store_db(db, user_password)

    def init_db(self, user_password: str) -> None:
        db = PasswordDB()
        self._store_db(db, user_password)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_db(self, user_password: str) -> PasswordDB:
        if not self._vault_file.exists():
            return PasswordDB()

        payload = self._vault_file.read_bytes()
        if len(payload) > _MAX_PAYLOAD_BYTES:
            raise WrongPasswordError()

        plaintext = decrypt(payload, user_password)
        if plaintext is None:
            raise WrongPasswordError()
        if len(plaintext) > _MAX_PLAINTEXT_BYTES:
            raise WrongPasswordError()

        data = json.loads(plaintext)
        found_ver = data.get("ver")
        if found_ver != CURRENT_DB_VERSION:
            raise UnsupportedDBVersionError(
                found_ver if isinstance(found_ver, str) else str(found_ver)
            )

        return PasswordDB(
            ver=data["ver"],
            entries=[PasswordEntry(**e) for e in data["entries"]],
        )

    def _store_db(self, db: PasswordDB, user_password: str) -> None:
        plaintext = json.dumps(asdict(db), ensure_ascii=False).encode("utf-8")
        payload = encrypt(plaintext, user_password)

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


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------


@dataclass
class PasswordDB:
    ver: str = CURRENT_DB_VERSION
    entries: list[PasswordEntry] = field(default_factory=list)


@dataclass
class PasswordEntry:
    name: str
    password: str
    modified: int  # Unix timestamp (UTC)


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------


class EntryAlreadyExistsError(Exception):
    def __init__(self, entry_name: str) -> None:
        self.entry_name = entry_name
        super().__init__(f"Entry for {entry_name!r} already exists")


class WrongPasswordError(Exception):
    def __init__(self) -> None:
        super().__init__("Wrong password or corrupted vault")


class UnsupportedDBVersionError(Exception):
    def __init__(self, found_version: str) -> None:
        self.found_version = found_version
        super().__init__(
            f"Unsupported vault version {found_version!r}. "
            f"Expected {CURRENT_DB_VERSION!r}. Please upgrade apass."
        )
