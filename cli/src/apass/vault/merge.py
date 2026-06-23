from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, cast

from pykeepass import Entry, Group, PyKeePass

from apass.vault.keepass import find_all_trashed, get_all_entries, get_title


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
    local_entries = {e.uuid: e for e in get_all_entries(local)}
    remote_trashed = {e.uuid for e in find_all_trashed(remote)}
    local_trashed = {e.uuid for e in find_all_trashed(local)}
    local_root_group = cast(Group, local.root_group)

    add = _mutate(dry_run, lambda entry: local_root_group.append(entry))
    trash = _mutate(dry_run, lambda entry: local.trash_entry(entry))
    drop = _mutate(dry_run, lambda entry: local.delete_entry(entry))
    rename = _mutate(dry_run, lambda entry, title: setattr(entry, "title", title))

    result = MergeResult()

    for remote_entry in get_all_entries(remote):
        local_entry = local_entries.get(remote_entry.uuid)
        duplicate_entry = _get_duplicate(remote_entry, local_entries.values())
        title = _format_title(remote_entry)

        if local_entry is None:
            add(remote_entry)

            if remote_entry.uuid in remote_trashed:
                trash(remote_entry)
                result.added_to_trash.append(title)
            else:
                result.added.append(title)
        elif _is_first_recent(remote_entry, local_entry):
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

        if duplicate_entry is not None:
            suffix = _get_new_suffix(duplicate_entry, local_entries.values())
            display_title = _format_title_with_suffix(duplicate_entry, suffix)
            rename(duplicate_entry, get_title(duplicate_entry) + suffix)
            trash(duplicate_entry)
            result.trashed.append(display_title)

    return result


def _format_title(entry: Entry) -> str:
    title = get_title(entry)
    username = entry.username or ""
    return f"{title}/{username}" if username else title


def _format_title_with_suffix(entry: Entry, suffix: str) -> str:
    title = get_title(entry)
    username = entry.username or ""
    titled = title + suffix
    return f"{titled}/{username}" if username else titled


def _mutate(dry_run: bool, action: Callable[..., None]) -> Callable[..., None]:
    if dry_run:
        return lambda _entry: None
    return action


def _get_duplicate(new: Entry, existing: Iterable[Entry]) -> Entry | None:
    duplicate = next(
        (e for e in existing if e.title == new.title and e.username == new.username and e.uuid != new.uuid),
        None,
    )
    if duplicate is not None:
        return duplicate if _is_first_recent(new, duplicate) else new
    return None


def _is_first_recent(first: Entry, second: Entry) -> bool:
    return cast(datetime, first.mtime) > cast(datetime, second.mtime)


def _get_new_suffix(new: Entry, existing: Iterable[Entry]) -> str:
    suffix = max(_get_suffix(get_title(e)) for e in existing if get_title(e).startswith(get_title(new)))
    return f"_{suffix+1}" if suffix > 0 else ""


def _get_suffix(title: str) -> int:
    splitted = title.split("_")
    if len(splitted) == 2:
        try:
            return int(splitted[1])
        except ValueError:
            pass
    return 0
