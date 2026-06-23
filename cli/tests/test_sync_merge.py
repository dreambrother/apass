from datetime import datetime, timedelta
from typing import Callable, cast
from uuid import UUID

from apass.vault import keepass
from pykeepass import Entry, PyKeePass

from apass.vault.merge import MergeResult, merge_dbs


def test_merge_empty_dbs(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    remote = kp_factory()

    result = merge_dbs(local, remote)

    assert result == MergeResult()
    assert local.entries == []


def test_merge_identical(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local_entry = local.add_entry(local.root_group, "local1", "", "")
    remote = kp_factory()
    remote_entry = remote.add_entry(remote.root_group, "local1", "", "")
    _set_uuid(remote_entry, local_entry.uuid)
    remote_entry.mtime = local_entry.mtime

    result = merge_dbs(local, remote)

    assert result == MergeResult()
    assert _has_entry(keepass.find_all_alive(local), "local1")


def test_merge_disjoint_entries(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local.add_entry(local.root_group, "local1", "user1", "pass1")
    local.add_entry(local.root_group, "local2", "user2", "pass2")
    remote = kp_factory()
    remote.add_entry(remote.root_group, "remote1", "user3", "pass3")
    remote.add_entry(remote.root_group, "remote2", "user4", "pass4")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["remote1", "remote2"])
    alive_entries = keepass.find_all_alive(local)
    assert len(alive_entries) == 4
    assert all([
        _has_entry(alive_entries, title, user_name, password)
        for title, user_name, password in
        [
            ("local1", "user1", "pass1"),
            ("local2", "user2", "pass2"),
            ("remote1", "user3", "pass3"),
            ("remote2", "user4", "pass4"),
        ]
    ])


# TODO must be changed
def test_merge_distinct_entries_with_same_title(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local.add_entry(local.root_group, "github", "alice", "local-secret")
    remote = kp_factory()
    remote.add_entry(remote.root_group, "github", "bob", "remote-secret")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["github"])
    alive_entries = keepass.find_all_alive(local)
    assert len(alive_entries) == 2
    assert _has_entry(alive_entries, "github", "alice", "local-secret")
    assert _has_entry(alive_entries, "github", "bob", "remote-secret")


def test_merge_trashed_and_restored(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    serv1_local = local.add_entry(local.root_group, "serv1", "user1", "pass1")
    to_trash_local = local.add_entry(local.root_group, "serv2", "user2", "pass2")
    local.trash_entry(to_trash_local)

    remote = kp_factory()
    to_trash_remote = remote.add_entry(remote.root_group, "serv1", "user1", "pass1")
    remote.trash_entry(to_trash_remote)
    _set_uuid(to_trash_remote, serv1_local.uuid)
    _bump_mtime(to_trash_remote)
    to_restore_remote = remote.add_entry(remote.root_group, "serv2", "user2", "pass2")
    _set_uuid(to_restore_remote, to_trash_local.uuid)
    _bump_mtime(to_restore_remote)

    result = merge_dbs(local, remote)

    assert result == MergeResult(trashed=["serv1"], restored_from_trash=["serv2"])

    alive_entries = keepass.find_all_alive(local)
    assert len(alive_entries) == 1
    assert _has_entry(alive_entries, "serv2")

    trashed_entries = keepass.find_all_trashed(local)
    assert len(trashed_entries) == 1
    assert _has_entry(trashed_entries, "serv1")


def test_merge_update(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    serv1_local = local.add_entry(local.root_group, "serv1", "user1", "pass1")
    not_changed_local = local.add_entry(local.root_group, "serv2", "user2", "pass2")

    remote = kp_factory()
    changed_remote = remote.add_entry(remote.root_group, "serv1", "user1", "pass111")
    _set_uuid(changed_remote, serv1_local.uuid)
    _bump_mtime(changed_remote)
    not_changed_remote = remote.add_entry(remote.root_group, "serv2", "user2", "pass2")
    _set_uuid(not_changed_remote, not_changed_local.uuid)
    not_changed_remote.mtime = not_changed_local.mtime

    result = merge_dbs(local, remote)

    assert result == MergeResult(updated=["serv1"])
    entries = keepass.find_all_alive(local)
    assert len(entries) == 2
    assert all([
        _has_entry(entries, title, user_name, password)
        for title, user_name, password in
        [
            ("serv1", "user1", "pass111"),
            ("serv2", "user2", "pass2"),
        ]
    ])


def test_merge_dry_run_does_not_mutate_local(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    serv1_local = local.add_entry(local.root_group, "serv1", "user1", "pass1")
    not_changed_local = local.add_entry(local.root_group, "serv2", "user2", "pass2")
    local_alive_titles = [e.title for e in keepass.find_all_alive(local)]
    local_trashed_titles = [e.title for e in keepass.find_all_trashed(local)]
    local_alive_count = len(local_alive_titles)

    remote = kp_factory()
    changed_remote = remote.add_entry(remote.root_group, "serv1", "user1", "pass111")
    _set_uuid(changed_remote, serv1_local.uuid)
    _bump_mtime(changed_remote)
    not_changed_remote = remote.add_entry(remote.root_group, "serv2", "user2", "pass2")
    _set_uuid(not_changed_remote, not_changed_local.uuid)
    not_changed_remote.mtime = not_changed_local.mtime
    remote.add_entry(remote.root_group, "serv3", "user3", "pass3")
    to_trash_remote = remote.add_entry(remote.root_group, "serv4", "user4", "pass4")
    remote.trash_entry(to_trash_remote)

    result = merge_dbs(local, remote, dry_run=True)

    assert result == MergeResult(updated=["serv1"], added=["serv3"], added_to_trash=["serv4"])

    # local не должен измениться: ни состав, ни количество, ни состояние (alive/trashed).
    assert [e.title for e in keepass.find_all_alive(local)] == local_alive_titles
    assert [e.title for e in keepass.find_all_trashed(local)] == local_trashed_titles
    alive = keepass.find_all_alive(local)
    assert len(alive) == local_alive_count
    assert _has_entry(alive, "serv1", "user1", "pass1")
    assert _has_entry(alive, "serv2", "user2", "pass2")


def test_merge_update_trashed(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    not_changed_local = local.add_entry(local.root_group, "serv1", "user1", "pass1")
    local.trash_entry(not_changed_local)
    serv2_local = local.add_entry(local.recyclebin_group, "serv2", "user2", "pass2")

    remote = kp_factory()
    not_changed_remote = remote.add_entry(remote.root_group, "serv1", "user1", "pass1")
    remote.trash_entry(not_changed_remote)
    _set_uuid(not_changed_remote, not_changed_local.uuid)
    not_changed_remote.mtime = not_changed_local.mtime
    changed_remote = remote.add_entry(remote.recyclebin_group, "serv2", "user22", "pass222")
    _set_uuid(changed_remote, serv2_local.uuid)
    _bump_mtime(changed_remote)
    remote.add_entry(remote.recyclebin_group, "serv3", "user3", "pass3")

    result = merge_dbs(local, remote)

    assert result == MergeResult(updated_in_trash=["serv2"], added_to_trash=["serv3"])
    entries = keepass.find_all_trashed(local)
    assert len(entries) == 3
    assert all([
        _has_entry(entries, title, user_name, password)
        for title, user_name, password in
        [
            ("serv1", "user1", "pass1"),
            ("serv2", "user22", "pass222"),
            ("serv3", "user3", "pass3"),
        ]
    ])


def _has_entry(entries: list[Entry], title: str, user_name: str | None = None, password: str | None = None) -> bool:
    return any(
        e.title == title
        and (user_name is None or e.username == user_name)
        and (password is None or e.password == password)
        for e in entries
    )


def _bump_mtime(entry: Entry) -> None:
    entry.mtime = cast(datetime, entry.mtime) + timedelta(seconds=1)


def _set_uuid(entry: Entry, value: UUID | str) -> None:
    """Override an entry's UUID. Used in tests to model a single entity
    existing on both local and remote sides after a sync round-trip."""
    entry.uuid = value if isinstance(value, UUID) else UUID(value)
