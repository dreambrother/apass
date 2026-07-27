import os
from pathlib import Path

ENV_DB_PATH = "APASS_DB_PATH"
APASS_DIR = Path.home() / ".apass"
DEFAULT_DB_PATH = APASS_DIR / "vault.kdbx"


def get_db_path() -> Path:
    env = os.environ.get(ENV_DB_PATH)
    if env:
        return Path(env)
    return DEFAULT_DB_PATH
