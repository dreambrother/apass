from dataclasses import dataclass, field
from typing import Literal

from apass.vault import PasswordDB, PasswordEntry


@dataclass
class MergeResult:
    merged_db: PasswordDB
    added: list[PasswordEntry] = field(default_factory=list)
    updated: list[PasswordEntry] = field(default_factory=list)
    kept_locally_only: list[PasswordEntry] = field(default_factory=list)
    kept_local_with_conflict: list[PasswordEntry] = field(default_factory=list)
    unchanged_count: int = 0


def merge_dbs(
    local: PasswordDB,
    remote: PasswordDB,
    prefer: Literal["local", "remote"] = "local",
) -> MergeResult:
    local_by_name = {e.name: e for e in local.entries}
    remote_by_name = {e.name: e for e in remote.entries}

    merged_entries: list[PasswordEntry] = []
    added: list[PasswordEntry] = []
    updated: list[PasswordEntry] = []
    kept_locally_only: list[PasswordEntry] = []
    kept_local_with_conflict: list[PasswordEntry] = []
    unchanged_count = 0

    for name, local_entry in local_by_name.items():
        if name not in remote_by_name:
            merged_entries.append(local_entry)
            kept_locally_only.append(local_entry)
        else:
            remote_entry = remote_by_name[name]
            winner = _resolve_conflict(local_entry, remote_entry, prefer)
            merged_entries.append(winner)
            if winner is local_entry:
                if (
                    local_entry.modified == remote_entry.modified
                    and local_entry.login == remote_entry.login
                    and local_entry.password == remote_entry.password
                ):
                    unchanged_count += 1
                else:
                    kept_local_with_conflict.append(local_entry)
            else:
                updated.append(remote_entry)

    for name, remote_entry in remote_by_name.items():
        if name not in local_by_name:
            merged_entries.append(remote_entry)
            added.append(remote_entry)

    merged_db = PasswordDB(ver=local.ver, entries=merged_entries)
    return MergeResult(
        merged_db=merged_db,
        added=added,
        updated=updated,
        kept_locally_only=kept_locally_only,
        kept_local_with_conflict=kept_local_with_conflict,
        unchanged_count=unchanged_count,
    )


def _resolve_conflict(
    local: PasswordEntry,
    remote: PasswordEntry,
    prefer: Literal["local", "remote"],
) -> PasswordEntry:
    if local.modified < remote.modified:
        return remote
    if local.modified > remote.modified:
        return local
    if local.password == remote.password:
        return local
    return local if prefer == "local" else remote
