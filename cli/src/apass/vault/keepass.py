from typing import Iterable, cast

from apass.vault.errors import CorruptedVaultError
from pykeepass import Entry, Group, PyKeePass


def find_alive(kp: PyKeePass, name: str) -> Entry | None:
    for e in find_all_alive(kp):
        if e.title == name:
            return e
    return None


def find_all_alive(kp: PyKeePass) -> list[Entry]:
    trashed = find_all_trashed(kp)
    return [e for e in cast(Iterable[Entry], kp.entries) if e not in trashed]


def find_trashed(kp: PyKeePass, name: str) -> Entry | None:
    for e in find_all_trashed(kp):
        if e.title == name:
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
