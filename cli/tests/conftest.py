from pathlib import Path
import random
import string
from typing import Any, Callable, cast

import pykeepass
import pykeepass.pykeepass as _pk
import pytest
from construct import Container

from apass.vault.db import Vault


@pytest.fixture(scope="session", autouse=True)
def _fast_argon2_blank(tmp_path_factory: pytest.TempPathFactory):
    """Replace pykeepass's blank database with a low-KDF copy.

    pykeepass's bundled ``blank_database.kdbx`` uses Argon2 with
    ``M=64 MiB, I=14, P=2`` which makes every ``PyKeePass`` open/save
    take ~0.4s. Generating a single low-cost blank once and pointing
    ``BLANK_DATABASE_LOCATION`` at it drops that to ~microseconds
    while keeping the full KDBX4 + Argon2id code path exercised.
    Production code is untouched.
    """
    tmp = tmp_path_factory.mktemp("apass-tests")
    new_blank = tmp / "blank.kdbx"

    kp = cast(Any, pykeepass.create_database(str(new_blank), password=_pk.BLANK_DATABASE_PASSWORD))
    p = kp.kdbx.header.value.dynamic_header.kdf_parameters.data.dict
    new_items = [
        Container(
            type=p[k].type,
            key=p[k].key,
            value=(1 if k == "I" else 8192 if k == "M" else 1 if k == "P" else p[k].value),
            next_byte=p[k].next_byte,
        )
        for k in p
    ]
    p.clear()
    p.update({item["key"]: item for item in new_items})
    # Drop the cached raw header bytes so construct re-encodes the mutated value
    del kp.kdbx.header.data
    kp.save()

    original_location = _pk.BLANK_DATABASE_LOCATION
    _pk.BLANK_DATABASE_LOCATION = str(new_blank)
    yield
    _pk.BLANK_DATABASE_LOCATION = original_location


@pytest.fixture
def vault_file(tmp_path: Path) -> Path:
    return tmp_path / "vault.kdbx"


@pytest.fixture
def master_password() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


@pytest.fixture
def initialized_vault(vault_file: Path, master_password: str) -> Vault:
    vault = Vault(vault_file)
    vault.init_db(master_password)
    return vault


@pytest.fixture(autouse=True)
def isolated_db_path(monkeypatch: pytest.MonkeyPatch, vault_file: Path) -> None:
    monkeypatch.setenv("APASS_DB_PATH", str(vault_file))


@pytest.fixture
def kp_factory(tmp_path: Path) -> Callable[[], pykeepass.PyKeePass]:
    index = 0
    def _make() -> pykeepass.PyKeePass:
        nonlocal index
        index += 1
        return pykeepass.create_database(f"{tmp_path}/kp-{index}.kdbx")
    return _make
