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


def test_merge_added_with_empty_username_omits_slash(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """With an empty username, MergeResult strings must omit the slash."""
    local = kp_factory()
    remote = kp_factory()
    remote.add_entry(remote.root_group, "wifi", "", "secret")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["wifi"])
    alive = keepass.find_all_alive(local)
    assert len(alive) == 1
    assert _has_entry(alive, "wifi", "", "secret")


def test_merge_duplicate_with_empty_username(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """A duplicate on (title, "") is deduplicated; the MergeResult string has no slash."""
    local = kp_factory()
    local_entry = local.add_entry(local.root_group, "wifi", "", "local-pass")
    _bump_mtime(local_entry)

    remote = kp_factory()
    remote.add_entry(remote.root_group, "wifi", "", "remote-pass")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["wifi"], trashed=["wifi"])

    alive = keepass.find_all_alive(local)
    assert len(alive) == 1
    assert _has_entry(alive, "wifi", "", "local-pass")

    trashed = keepass.find_all_trashed(local)
    assert len(trashed) == 1
    assert _has_entry(trashed, "wifi", "", "remote-pass")


def test_merge_disjoint_entries(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local.add_entry(local.root_group, "local1", "user1", "pass1")
    local.add_entry(local.root_group, "local2", "user2", "pass2")
    remote = kp_factory()
    remote.add_entry(remote.root_group, "remote1", "user3", "pass3")
    remote.add_entry(remote.root_group, "remote2", "user4", "pass4")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["remote1/user3", "remote2/user4"])
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


def test_merge_non_unique_entry(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local_entry = local.add_entry(local.root_group, "github", "alice", "local-secret")
    _bump_mtime(local_entry)

    remote = kp_factory()
    remote.add_entry(remote.root_group, "github", "alice", "remote-secret")

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["github/alice"], trashed=["github/alice"])

    alive_entries = keepass.find_all_alive(local)
    assert len(alive_entries) == 1
    assert _has_entry(alive_entries, "github", "alice", "local-secret")

    trashed_entries = keepass.find_all_trashed(local)
    assert len(trashed_entries) == 1
    assert _has_entry(trashed_entries, "github", "alice", "remote-secret")


def test_merge_duplicate_remote_newer_keeps_remote_in_alive(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Duplicate where remote is newer: duplicate_entry = local. The local
    entry is renamed and trashed; remote stays alive."""
    local = kp_factory()
    local.add_entry(local.root_group, "github", "alice", "local-pass")

    remote = kp_factory()
    remote_entry = remote.add_entry(remote.root_group, "github", "alice", "remote-pass")
    _bump_mtime(remote_entry)

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["github/alice"], trashed=["github/alice"])

    alive = keepass.find_all_alive(local)
    assert len(alive) == 1
    assert _has_entry(alive, "github", "alice", "remote-pass")

    trashed = keepass.find_all_trashed(local)
    assert len(trashed) == 1
    assert _has_entry(trashed, "github", "alice", "local-pass")


def test_merge_non_unique_entry_with_suffix(kp_factory: Callable[[], PyKeePass]) -> None:
    local = kp_factory()
    local1 = local.add_entry(local.root_group, "github", "petr", "local-secret")
    local2 = local.add_entry(local.root_group, "github_1", "petr", "local-secret")
    local3 = local.add_entry(local.root_group, "github_3", "petr", "local-secret")
    local4 = local.add_entry(local.root_group, "githubasd", "petr", "local-secret")
    local5 = local.add_entry(local.root_group, "github_asd", "petr", "local-secret")
    local.add_entry(local.root_group, "gitlab", "alice", "local-secret")
    local.trash_entry(local2)
    local.trash_entry(local3)
    local.trash_entry(local4)
    local.trash_entry(local5)
    _bump_mtime(local1)

    remote = kp_factory()
    remote.add_entry(remote.root_group, "github", "petr", "remote-secret")
    remote_gitlab = remote.add_entry(remote.root_group, "gitlab", "alice", "remote-secret")
    _bump_mtime(remote_gitlab)

    result = merge_dbs(local, remote)

    assert result == MergeResult(added=["github/petr", "gitlab/alice"], trashed=["github_4/petr", "gitlab/alice"])

    alive_entries = keepass.find_all_alive(local)
    assert len(alive_entries) == 2
    assert _has_entry(alive_entries, "github", "petr", "local-secret")
    assert _has_entry(alive_entries, "gitlab", "alice", "remote-secret")

    trashed_entries = keepass.find_all_trashed(local)
    assert len(trashed_entries) == 6
    assert _has_entry(trashed_entries, "github_1", "petr", "local-secret")
    assert _has_entry(trashed_entries, "github_3", "petr", "local-secret")
    assert _has_entry(trashed_entries, "githubasd", "petr", "local-secret")
    assert _has_entry(trashed_entries, "github_asd", "petr", "local-secret")
    assert _has_entry(trashed_entries, "github_4", "petr", "remote-secret")
    assert _has_entry(trashed_entries, "gitlab", "alice", "local-secret")


def test_merge_multiple_duplicates_suffixes_independent(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Multiple duplicates in one merge: suffixes are computed relative to
    their own titles, without crossing over."""
    local = kp_factory()
    # gitlab/alice already has _1, so the new duplicate must get _2.
    local_gitlab = local.add_entry(local.root_group, "gitlab", "alice", "local-pass")
    local_gitlab_1 = local.add_entry(local.root_group, "gitlab_1", "alice", "local-pass")
    local.trash_entry(local_gitlab_1)
    # aws/bob has no siblings, so no suffix will be appended.
    local_aws = local.add_entry(local.root_group, "aws", "bob", "local-pass")
    _bump_mtime(local_aws)
    _bump_mtime(local_gitlab)

    remote = kp_factory()
    remote.add_entry(remote.root_group, "gitlab", "alice", "remote-pass")
    remote.add_entry(remote.root_group, "aws", "bob", "remote-pass")

    result = merge_dbs(local, remote)

    assert result == MergeResult(
        added=["gitlab/alice", "aws/bob"],
        trashed=["gitlab_2/alice", "aws/bob"],
    )

    alive = keepass.find_all_alive(local)
    assert _has_entry(alive, "gitlab", "alice", "local-pass")
    assert _has_entry(alive, "aws", "bob", "local-pass")

    trashed = keepass.find_all_trashed(local)
    # gitlab_1 (original) + gitlab_2 (new duplicate) + aws/bob (new duplicate)
    assert _has_entry(trashed, "gitlab_1", "alice", "local-pass")
    assert _has_entry(trashed, "gitlab_2", "alice", "remote-pass")
    assert _has_entry(trashed, "aws", "bob", "remote-pass")


def test_merge_same_title_different_username_not_duplicate(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Same title but a different username is not a duplicate."""
    local = kp_factory()
    local_alice = local.add_entry(local.root_group, "github", "alice", "local-pass")
    _bump_mtime(local_alice)

    remote = kp_factory()
    remote.add_entry(remote.root_group, "github", "alice", "remote-pass")
    remote.add_entry(remote.root_group, "github", "bob", "remote-pass-bob")

    result = merge_dbs(local, remote)

    # alice: add(remote) (uuid did not match) + duplicate(remote) -> trashed.
    # bob: no local entry, remote has one -> added.
    assert result == MergeResult(
        added=["github/alice", "github/bob"],
        trashed=["github/alice"],
    )

    alive = keepass.find_all_alive(local)
    assert _has_entry(alive, "github", "alice", "local-pass")
    assert _has_entry(alive, "github", "bob", "remote-pass-bob")

    trashed = keepass.find_all_trashed(local)
    assert _has_entry(trashed, "github", "alice", "remote-pass")


def test_merge_two_remote_entries_same_title_username(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Two remote entries with the same (title, username) but different uuids.

    Current behavior: local_entries is built once at the start of merge_dbs
    (snapshot), so the first remote entry, once added to local, is not
    visible as a duplicate for the second one. Both entries end up alive
    in local. This test pins down the current behavior.
    """
    local = kp_factory()

    remote = kp_factory()
    remote.add_entry(remote.root_group, "github", "alice", "remote-pass-1")
    remote.add_entry(
        remote.root_group, "github", "alice", "remote-pass-2", force_creation=True
    )

    result = merge_dbs(local, remote)

    assert result == MergeResult(
        added=["github/alice", "github/alice"],
    )

    alive = keepass.find_all_alive(local)
    assert len(alive) == 2
    passwords = sorted(e.password or "" for e in alive)
    assert passwords == ["remote-pass-1", "remote-pass-2"]


def test_merge_uuid_match_with_duplicate_in_local(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Uuid matches (so it is an update) and there is also a (title, username)
    duplicate in local with a different uuid that must be deduplicated too.

    Scenario: local has alive `github/alice` (uuid X) and trashed
    `github/alice` (uuid Y). Remote has `github/alice` (uuid X, newer).
    Expected: update by uuid + duplicate branch for Y (found among local
    by (title, username), not matching X, so it gets processed).
    """
    local = kp_factory()
    local_alive = local.add_entry(local.root_group, "github", "alice", "old-pass")
    _bump_mtime(local_alive)
    local_trashed = local.add_entry(
        local.root_group, "github", "alice", "stale-pass", force_creation=True
    )
    local.trash_entry(local_trashed)

    remote = kp_factory()
    remote_entry = remote.add_entry(remote.root_group, "github", "alice", "new-pass")
    _set_uuid(remote_entry, local_alive.uuid)
    _bump_mtime(remote_entry)
    _bump_mtime(remote_entry)

    result = merge_dbs(local, remote)

    # update by uuid X (alive) + duplicate branch for Y (trashed):
    # _get_duplicate finds Y; _is_first_recent(remote, Y) is True since
    # remote is newer, so duplicate = Y. Then rename(Y) + trash(Y) — Y is
    # already trashed, so it stays trashed; the trashed list in MergeResult
    # gets "github/alice" appended.
    assert result == MergeResult(
        updated=["github/alice"],
        trashed=["github/alice"],
    )

    alive = keepass.find_all_alive(local)
    assert _has_entry(alive, "github", "alice", "new-pass")

    trashed = keepass.find_all_trashed(local)
    passwords = sorted(e.password or "" for e in trashed)
    # The original Y (stale-pass) stays in trashed; X (new-pass) is alive.
    assert passwords == ["stale-pass"]


def test_merge_local_trashed_with_equal_mtime_noop(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """local-trashed + remote-alive with the same uuid and equal mtime: no-op."""
    local = kp_factory()
    serv1_local = local.add_entry(local.root_group, "serv1", "user1", "pass1")
    local.trash_entry(serv1_local)

    remote = kp_factory()
    serv1_remote = remote.add_entry(remote.root_group, "serv1", "user1", "pass1")
    _set_uuid(serv1_remote, serv1_local.uuid)
    serv1_remote.mtime = serv1_local.mtime

    result = merge_dbs(local, remote)

    assert result == MergeResult()
    assert _has_entry(keepass.find_all_trashed(local), "serv1", "user1", "pass1")
    assert keepass.find_all_alive(local) == []


def test_merge_empty_remote_keeps_local_unchanged(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """Empty remote: local is not modified, MergeResult is empty."""
    local = kp_factory()
    local.add_entry(local.root_group, "serv1", "user1", "pass1")
    local.add_entry(local.root_group, "serv2", "user2", "pass2")
    local_alive = [e.title for e in keepass.find_all_alive(local)]
    local_trashed = [e.title for e in keepass.find_all_trashed(local)]

    remote = kp_factory()

    result = merge_dbs(local, remote)

    assert result == MergeResult()
    assert [e.title for e in keepass.find_all_alive(local)] == local_alive
    assert [e.title for e in keepass.find_all_trashed(local)] == local_trashed


def test_merge_duplicate_with_remote_entry_already_trashed(
    kp_factory: Callable[[], PyKeePass],
) -> None:
    """The remote duplicate is already in the recycle bin: it shows up both
    in added_to_trash and in trashed (via the duplicate branch)."""
    local = kp_factory()
    local_entry = local.add_entry(local.root_group, "github", "alice", "local-pass")
    _bump_mtime(local_entry)

    remote = kp_factory()
    remote_entry = remote.add_entry(remote.root_group, "github", "alice", "remote-pass")
    remote.trash_entry(remote_entry)

    result = merge_dbs(local, remote)

    assert result == MergeResult(
        added_to_trash=["github/alice"],
        trashed=["github/alice"],
    )

    alive = keepass.find_all_alive(local)
    assert _has_entry(alive, "github", "alice", "local-pass")

    trashed = keepass.find_all_trashed(local)
    assert _has_entry(trashed, "github", "alice", "remote-pass")


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

    assert result == MergeResult(trashed=["serv1/user1"], restored_from_trash=["serv2/user2"])

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

    assert result == MergeResult(updated=["serv1/user1"])
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

    assert result == MergeResult(updated=["serv1/user1"], added=["serv3/user3"], added_to_trash=["serv4/user4"])

    # local must be unchanged: composition, count, and alive/trashed state.
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

    assert result == MergeResult(updated_in_trash=["serv2/user22"], added_to_trash=["serv3/user3"])
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
    entry.mtime = cast(datetime, entry.mtime) + timedelta(seconds=5)


def _set_uuid(entry: Entry, value: UUID | str) -> None:
    """Override an entry's UUID. Used in tests to model a single entity
    existing on both local and remote sides after a sync round-trip."""
    entry.uuid = value if isinstance(value, UUID) else UUID(value)
