import io
from typing import Iterable, cast

from pykeepass import Entry, Group, PyKeePass
from pykeepass.exceptions import (
    CredentialsError,
    HeaderChecksumError,
    PayloadChecksumError,
)

from apass.vault.errors import CorruptedVaultError, WrongPasswordError


__all__ = [
    "from_bytes",
    "is_valid",
    "matches",
    "find_alive",
    "find_all_alive",
    "find_trashed",
    "find_all_trashed",
    "get_all_entries",
    "validate_entries",
]


def from_bytes(db_bytes: bytes, master_password: str) -> PyKeePass:
    try:
        kp = PyKeePass(io.BytesIO(db_bytes), password=master_password)
    except CredentialsError as e:
        raise WrongPasswordError() from e
    except (HeaderChecksumError, PayloadChecksumError) as e:
        raise CorruptedVaultError() from e
    except (OSError, ValueError) as e:
        raise CorruptedVaultError() from e
    validate_entries(kp)
    return kp


def is_valid(db_bytes: bytes, master_password: str) -> bool:
    try:
        _ = from_bytes(db_bytes, master_password)
    except (WrongPasswordError, CorruptedVaultError):
        return False
    return True


def matches(entry: Entry, query: str) -> bool:
    if entry.title is None:
        return False
    return query.lower() in entry.title.lower()


def find_alive(kp: PyKeePass, name: str, login: str) -> Entry | None:
    for e in find_all_alive(kp):
        if e.title == name and (e.username or "") == login:
            return e
    return None


def find_all_alive(kp: PyKeePass) -> list[Entry]:
    trashed = find_all_trashed(kp)
    return [e for e in cast(Iterable[Entry], kp.entries) if e not in trashed]


def find_trashed(kp: PyKeePass, name: str, login: str) -> Entry | None:
    for e in find_all_trashed(kp):
        if e.title == name and (e.username or "") == login:
            return e
    return None


def find_all_trashed(kp: PyKeePass) -> list[Entry]:
    recycle = cast(Group | None, kp.recyclebin_group)
    return recycle.entries if recycle is not None else []


def get_all_entries(kp: PyKeePass) -> list[Entry]:
    return cast(list[Entry], kp.entries)


def validate_entries(kp: PyKeePass) -> None:
    """Ensure every entry has a non-empty title and password.

    apass does not yet support entries without a title or password,
    so we fail fast at load time rather than at every read site.
    """
    for e in cast(Iterable[Entry], kp.entries):
        if not e.title:
            raise CorruptedVaultError("Empty entry title is not supported yet")
        if not e.password:
            raise CorruptedVaultError("Empty entry password is not supported yet")
