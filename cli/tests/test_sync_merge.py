from uuid import uuid4

from apass.sync.merge import merge_dbs
from apass.vault import PasswordDB, PasswordEntry


def _entry(name: str, modified: int, login: str | None = None, password: str = "p") -> PasswordEntry:
    return PasswordEntry(uuid=uuid4(), name=name, login=login, password=password, modified=modified)


def test_merge_empty_dbs() -> None:
    local = PasswordDB(entries=[])
    remote = PasswordDB(entries=[])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 0
    assert len(result.merged_db.trashed) == 0
    assert len(result.added) == 0
    assert len(result.updated) == 0
    assert len(result.kept_locally_only) == 0
    assert result.unchanged_count == 0


def test_merge_disjoint_entries() -> None:
    local = PasswordDB(entries=[_entry("local1", 1000)])
    remote = PasswordDB(entries=[_entry("remote1", 1000, login="user2", password="pass2")])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 2
    names = {e.name for e in result.merged_db.entries}
    assert names == {"local1", "remote1"}
    assert len(result.added) == 1
    assert result.added[0].name == "remote1"
    assert len(result.kept_locally_only) == 1
    assert result.kept_locally_only[0].name == "local1"


def test_merge_same_entry_local_newer() -> None:
    uid = uuid4()
    local = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="local_user", password="local_pass", modified=2000)])
    remote = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="remote_user", password="remote_pass", modified=1000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.name == "example"
    assert entry.login == "local_user"
    assert entry.password == "local_pass"
    assert entry.modified == 2000
    assert len(result.updated) == 0
    assert len(result.kept_local_with_conflict) == 1
    assert result.kept_local_with_conflict[0].name == "example"


def test_merge_same_entry_remote_newer() -> None:
    uid = uuid4()
    local = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="local_user", password="local_pass", modified=1000)])
    remote = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="remote_user", password="remote_pass", modified=2000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.name == "example"
    assert entry.login == "remote_user"
    assert entry.password == "remote_pass"
    assert entry.modified == 2000
    assert len(result.updated) == 1
    assert result.updated[0].name == "example"


def test_merge_same_entry_same_time_local_wins() -> None:
    uid = uuid4()
    local = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="user", password="local_pass", modified=1000)])
    remote = PasswordDB(entries=[PasswordEntry(uuid=uid, name="example", login="user", password="remote_pass", modified=1000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.password == "local_pass"
    assert len(result.kept_local_with_conflict) == 1
    assert result.kept_local_with_conflict[0].name == "example"


def test_merge_same_entry_identical() -> None:
    e = _entry("example", 1000, "user", "same_pass")
    local = PasswordDB(entries=[e])
    remote = PasswordDB(entries=[e])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    assert result.unchanged_count == 1
    assert len(result.updated) == 0


def test_merge_case_sensitive_names() -> None:
    local = PasswordDB(entries=[_entry("Example", 1000, password="pass1")])
    remote = PasswordDB(entries=[_entry("example", 2000, password="pass2")])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 2
    names = {e.name for e in result.merged_db.entries}
    assert names == {"Example", "example"}


def test_merge_complex_scenario() -> None:
    keep_local_uid = uuid4()
    update_uid = uuid4()
    local_only_uid = uuid4()
    unchanged_uid = uuid4()
    remote_only_uid = uuid4()

    local = PasswordDB(entries=[
        PasswordEntry(uuid=keep_local_uid, name="keep_local", login=None, password="pass1", modified=2000),
        PasswordEntry(uuid=update_uid, name="update_from_remote", login=None, password="old", modified=1000),
        PasswordEntry(uuid=local_only_uid, name="local_only", login=None, password="pass3", modified=1000),
        PasswordEntry(uuid=unchanged_uid, name="unchanged", login="unch", password="same", modified=1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry(uuid=keep_local_uid, name="keep_local", login=None, password="remote", modified=1000),
        PasswordEntry(uuid=update_uid, name="update_from_remote", login=None, password="new", modified=2000),
        PasswordEntry(uuid=remote_only_uid, name="remote_only", login=None, password="pass4", modified=1000),
        PasswordEntry(uuid=unchanged_uid, name="unchanged", login="unch", password="same", modified=1000),
    ])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 5
    by_name = {e.name: e for e in result.merged_db.entries}

    assert by_name["keep_local"].password == "pass1"
    assert by_name["update_from_remote"].password == "new"
    assert by_name["local_only"].password == "pass3"
    assert by_name["remote_only"].password == "pass4"
    assert by_name["unchanged"].password == "same"

    assert len(result.added) == 1
    assert result.added[0].name == "remote_only"
    assert len(result.updated) == 1
    assert result.updated[0].name == "update_from_remote"
    assert len(result.kept_locally_only) == 1
    assert result.kept_locally_only[0].name == "local_only"
    assert len(result.kept_local_with_conflict) == 1
    assert result.kept_local_with_conflict[0].name == "keep_local"
    assert result.unchanged_count == 1


def test_merge_alive_vs_trash_remote_newer() -> None:
    uid = uuid4()
    local = PasswordDB(entries=[PasswordEntry(uuid=uid, name="github", login=None, password="alive_pass", modified=1000)])
    remote = PasswordDB(trashed=[PasswordEntry(uuid=uid, name="github", login=None, password="p", modified=2000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 0
    assert len(result.merged_db.trashed) == 1
    assert result.merged_db.trashed[0].modified == 2000


def test_merge_alive_vs_trash_local_newer() -> None:
    uid = uuid4()
    local = PasswordDB(entries=[PasswordEntry(uuid=uid, name="github", login=None, password="alive_pass", modified=2000)])
    remote = PasswordDB(trashed=[PasswordEntry(uuid=uid, name="github", login=None, password="p", modified=1000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    assert result.merged_db.entries[0].modified == 2000
    assert len(result.merged_db.trashed) == 0


def test_merge_both_trashed_latest_wins() -> None:
    uid = uuid4()
    local = PasswordDB(trashed=[PasswordEntry(uuid=uid, name="github", login=None, password="p", modified=1000)])
    remote = PasswordDB(trashed=[PasswordEntry(uuid=uid, name="github", login=None, password="p", modified=2000)])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 0
    assert len(result.merged_db.trashed) == 1
    assert result.merged_db.trashed[0].modified == 2000


def test_merge_trash_entry_persists_unchanged() -> None:
    e = _entry("github", 1000)
    local = PasswordDB(trashed=[e])
    remote = PasswordDB(trashed=[e])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.trashed) == 1
    assert result.unchanged_count == 1
