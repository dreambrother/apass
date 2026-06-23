from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, cast
from uuid import UUID

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
    local_entries: dict[UUID, Entry] = {
        e.uuid: e for e in get_all_entries(local)
    }
    remote_trashed: set[UUID] = {
        e.uuid for e in find_all_trashed(remote)
    }
    local_trashed: set[UUID] = {
        e.uuid for e in find_all_trashed(local)
    }
    local_root_group = cast(Group, local.root_group)

    add = _mutate(dry_run, lambda entry: local_root_group.append(entry))
    trash = _mutate(dry_run, lambda entry: local.trash_entry(entry))
    drop = _mutate(dry_run, lambda entry: local.delete_entry(entry))

    result = MergeResult()

    # TODO deduplication
    for remote_entry in get_all_entries(remote):
        local_entry = local_entries.get(remote_entry.uuid)
        title = cast(str, remote_entry.title)
        if local_entry is None:
            add(remote_entry)
            if remote_entry.uuid in remote_trashed:
                trash(remote_entry)
                result.added_to_trash.append(title)
            else:
                result.added.append(title)
        elif _is_remote_recent(local_entry, remote_entry):
            drop(local_entry)
            add(remote_entry)

            if remote_entry.uuid in remote_trashed:
                if remote_entry.uuid in local_trashed:
                    result.updated_in_trash.append(title)
                else:
                    result.trashed.append(title)
                trash(remote_entry)
            else:
                if remote_entry.uuid in local_trashed:
                    result.restored_from_trash.append(title)
                else:
                    result.updated.append(title)

    return result


def _is_remote_recent(local: Entry, remote: Entry) -> bool:
    return cast(datetime, remote.mtime) > cast(datetime, local.mtime)


def _mutate(dry_run: bool, action: Callable[[Entry], None]) -> Callable[[Entry], None]:
    if dry_run:
        return lambda _entry: None
    return action
