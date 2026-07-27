from datetime import UTC, datetime
from pathlib import Path

from apass.config import APASS_DIR

BACKUP_PREFIX = "vault-"
BACKUP_SUFFIX = ".kdbx"
MAX_BACKUPS = 10


def create_backup(vault_path: Path, now: datetime | None = None) -> Path | None:
    if not vault_path.exists():
        return None

    backup_dir = APASS_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    dest = _backup_path(now)
    dest.write_bytes(vault_path.read_bytes())
    dest.chmod(0o600)

    _prune_backups()
    return dest


def _backup_path(now: datetime | None = None) -> Path:
    ts = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return APASS_DIR / "backups" / f"{BACKUP_PREFIX}{ts}{BACKUP_SUFFIX}"


def _prune_backups() -> None:
    backup_dir = APASS_DIR / "backups"
    if not backup_dir.exists():
        return

    backups = sorted(
        (p for p in backup_dir.iterdir() if p.is_file() and _is_backup(p)),
        key=lambda p: p.name,
    )
    for old in backups[: max(0, len(backups) - MAX_BACKUPS)]:
        old.unlink()


def _is_backup(path: Path) -> bool:
    return path.name.startswith(BACKUP_PREFIX) and path.name.endswith(BACKUP_SUFFIX)
