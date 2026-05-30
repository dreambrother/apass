import os
import typing as t

import typer

from apass import clipboard, generator
from apass.config import ENV_DB_PATH, get_db_path
from apass.vault import Vault

app = typer.Typer()
_vault: Vault | None = None


@app.callback()
def callback():
    """APass — password manager."""


@app.command()
def init() -> None:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        typer.echo(f"Vault already exists at {path}", err=True)
        raise typer.Exit(1)
    user_password = typer.prompt(
        "Master password", hide_input=True, confirmation_prompt=True
    )
    vault = _get_vault()
    vault.init_db(user_password)
    if ENV_DB_PATH not in os.environ:
        typer.echo(f"No APASS_DB_PATH set, using {path}")
    typer.echo(f"Vault created at {path}")


@app.command()
def create(name: t.Annotated[str, typer.Argument(help="Service/utility name")]) -> None:
    """Create new password and copy it to the clipboard"""
    service_password = generator.create_password()
    user_password = typer.prompt("Master password", hide_input=True)
    vault = _get_vault()
    vault.create(name, service_password, user_password)
    clipboard.copy(service_password)


def _get_vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault(get_db_path())
    return _vault
