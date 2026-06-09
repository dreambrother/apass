import os
import tempfile
from pathlib import Path


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix="." + path.name + ".",
        suffix=".tmp",
    )
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)

    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)
