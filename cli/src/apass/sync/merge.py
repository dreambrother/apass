from dataclasses import dataclass, field

from apass.vault import PasswordDB, PasswordEntry


@dataclass
class MergeResult:
    merged_db: PasswordDB
    added: list[PasswordEntry] = field(default_factory=list)
    updated: list[PasswordEntry] = field(default_factory=list)
    kept_locally_only: list[PasswordEntry] = field(default_factory=list)
    kept_local_with_conflict: list[PasswordEntry] = field(default_factory=list)
    unchanged_count: int = 0


@dataclass
class _Side:
    entry: PasswordEntry
    is_trashed: bool
    is_local: bool


def merge_dbs(local: PasswordDB, remote: PasswordDB) -> MergeResult:
    local_by_uuid = _index(local, is_local=True)
    remote_by_uuid = _index(remote, is_local=False)

    all_uuids = set(local_by_uuid) | set(remote_by_uuid)

    merged_alive: list[PasswordEntry] = []
    merged_trash: list[PasswordEntry] = []

    added: list[PasswordEntry] = []
    updated: list[PasswordEntry] = []
    kept_locally_only: list[PasswordEntry] = []
    kept_local_with_conflict: list[PasswordEntry] = []
    unchanged_count = 0

    for uid in all_uuids:
        sides = local_by_uuid.get(uid, []) + remote_by_uuid.get(uid, [])
        winner = _pick_winner(sides)
        if winner.is_trashed:
            merged_trash.append(winner.entry)
        else:
            merged_alive.append(winner.entry)

        locals_ = [s for s in sides if s.is_local]
        remotes = [s for s in sides if not s.is_local]

        if len(sides) == 1:
            if sides[0].is_local:
                kept_locally_only.append(winner.entry)
            else:
                added.append(winner.entry)
            continue

        local_entry = locals_[0].entry if locals_ else None
        remote_entry = remotes[0].entry if remotes else None

        if local_entry is not None and remote_entry is not None:
            if winner.is_local and _same_content(local_entry, remote_entry):
                unchanged_count += 1
            elif winner.is_local:
                kept_local_with_conflict.append(winner.entry)
            else:
                updated.append(winner.entry)

    merged_db = PasswordDB(ver=local.ver, entries=merged_alive, trashed=merged_trash)
    return MergeResult(
        merged_db=merged_db,
        added=added,
        updated=updated,
        kept_locally_only=kept_locally_only,
        kept_local_with_conflict=kept_local_with_conflict,
        unchanged_count=unchanged_count,
    )


def _index(db: PasswordDB, *, is_local: bool) -> dict[object, list[_Side]]:
    result: dict[object, list[_Side]] = {}
    for e in db.entries:
        result.setdefault(e.uuid, []).append(_Side(e, False, is_local))
    for e in db.trashed:
        result.setdefault(e.uuid, []).append(_Side(e, True, is_local))
    return result


def _pick_winner(sides: list[_Side]) -> _Side:
    return max(sides, key=lambda s: (s.entry.modified, 1 if s.is_local else 0))


def _same_content(a: PasswordEntry, b: PasswordEntry) -> bool:
    return (
        a.login == b.login
        and a.password == b.password
        and a.modified == b.modified
    )
