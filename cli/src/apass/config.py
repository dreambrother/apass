import os
from pathlib import Path

ENV_DB_PATH = "APASS_DB_PATH"
DEFAULT_DB_PATH = Path.home() / ".apass" / "vault.kdbx"


def get_db_path() -> Path:
    env = os.environ.get(ENV_DB_PATH)
    if env:
        return Path(env)
    return DEFAULT_DB_PATH
