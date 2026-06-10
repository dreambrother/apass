from apass.sync.merge import merge_dbs
from apass.vault import PasswordDB, PasswordEntry


def test_merge_empty_dbs() -> None:
    local = PasswordDB(entries=[])
    remote = PasswordDB(entries=[])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 0
    assert len(result.added) == 0
    assert len(result.updated) == 0
    assert len(result.kept_locally_only) == 0
    assert result.unchanged_count == 0


def test_merge_disjoint_entries() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("local1", None, "pass1", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("remote1", "user2", "pass2", 1000),
    ])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 2
    names = {e.name for e in result.merged_db.entries}
    assert names == {"local1", "remote1"}
    assert len(result.added) == 1
    assert result.added[0].name == "remote1"
    assert len(result.kept_locally_only) == 1
    assert result.kept_locally_only[0].name == "local1"


def test_merge_same_entry_local_newer() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("example", "local_user", "local_pass", 2000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", "remote_user", "remote_pass", 1000),
    ])

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
    local = PasswordDB(entries=[
        PasswordEntry("example", "local_user", "local_pass", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", "remote_user", "remote_pass", 2000),
    ])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.name == "example"
    assert entry.login == "remote_user"
    assert entry.password == "remote_pass"
    assert entry.modified == 2000
    assert len(result.updated) == 1
    assert result.updated[0].name == "example"


def test_merge_same_entry_same_time_prefer_local() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("example", None, "local_pass", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", None, "remote_pass", 1000),
    ])

    result = merge_dbs(local, remote, prefer="local")

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.password == "local_pass"
    assert len(result.kept_local_with_conflict) == 1
    assert result.kept_local_with_conflict[0].name == "example"


def test_merge_same_entry_same_time_prefer_remote() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("example", "user", "local_pass", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", "user", "remote_pass", 1000),
    ])

    result = merge_dbs(local, remote, prefer="remote")

    assert len(result.merged_db.entries) == 1
    entry = result.merged_db.entries[0]
    assert entry.password == "remote_pass"


def test_merge_same_entry_identical() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("example", "user", "same_pass", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", "user", "same_pass", 1000),
    ])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 1
    assert result.unchanged_count == 1
    assert len(result.updated) == 0


def test_merge_case_sensitive_names() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("Example", None, "pass1", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("example", None, "pass2", 2000),
    ])

    result = merge_dbs(local, remote)

    assert len(result.merged_db.entries) == 2
    names = {e.name for e in result.merged_db.entries}
    assert names == {"Example", "example"}


def test_merge_complex_scenario() -> None:
    local = PasswordDB(entries=[
        PasswordEntry("keep_local", None, "pass1", 2000),
        PasswordEntry("update_from_remote", None, "old", 1000),
        PasswordEntry("local_only", None, "pass3", 1000),
        PasswordEntry("unchanged", "unch", "same", 1000),
    ])
    remote = PasswordDB(entries=[
        PasswordEntry("keep_local", None, "remote", 1000),
        PasswordEntry("update_from_remote", None, "new", 2000),
        PasswordEntry("remote_only", None, "pass4", 1000),
        PasswordEntry("unchanged", "unch", "same", 1000),
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
