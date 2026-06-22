from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, cast

from pykeepass import Entry, Group, PyKeePass

from apass.vault.keepass import find_all_trashed, get_all_entries


@dataclass
class MergeResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    trashed: list[str] = field(default_factory=list)
    added_to_trash: list[str] = field(default_factory=list)
    updated_in_trash: list[str] = field(default_factory=list)
    restored_from_trash: list[str] = field(default_factory=list)


def merge_dbs(
    local: PyKeePass, remote: PyKeePass, dry_run: bool = False
) -> MergeResult:
    local_entries = {
        cast(str, e.title): e for e in get_all_entries(local)
    }
    remote_trashed = {
        cast(str, e.title) for e in find_all_trashed(remote)
    }
    local_trashed = {
        cast(str, e.title) for e in find_all_trashed(local)
    }
    local_root_group = cast(Group, local.root_group)

    add = _mutate(dry_run, lambda entry: local_root_group.append(entry))
    trash = _mutate(dry_run, lambda entry: local.trash_entry(entry))
    drop = _mutate(dry_run, lambda entry: local.delete_entry(entry))

    result = MergeResult()

    for remote_entry in get_all_entries(remote):
        entry_title = cast(str, remote_entry.title)
        local_entry = local_entries.get(entry_title)
        if local_entry is None:
            add(remote_entry)
            if entry_title in remote_trashed:
                trash(remote_entry)
                result.added_to_trash.append(entry_title)
            else:
                result.added.append(entry_title)
        elif _is_remote_recent(local_entry, remote_entry):
            drop(local_entry)
            add(remote_entry)

            if entry_title in remote_trashed:
                if entry_title in local_trashed:
                    result.updated_in_trash.append(entry_title)
                else:
                    result.trashed.append(entry_title)
                trash(remote_entry)
            else:
                if entry_title in local_trashed:
                    result.restored_from_trash.append(entry_title)
                else:
                    result.updated.append(entry_title)

    return result


def _is_remote_recent(local: Entry, remote: Entry) -> bool:
    return cast(datetime, remote.mtime) > cast(datetime, local.mtime)


def _mutate(dry_run: bool, action: Callable[[Entry], None]) -> Callable[[Entry], None]:
    if dry_run:
        return lambda _entry: None
    return action
