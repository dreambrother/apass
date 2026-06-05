import os
import typing as t

import typer

from apass import clipboard, generator
from apass.config import ENV_DB_PATH, get_db_path
from apass.vault import EntryAlreadyExistsError, Vault

app = typer.Typer()
_vault: Vault | None = None


@app.callback()
def callback():
    """APass — password manager."""


# TODO master password to args
@app.command()
def init() -> None:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _fail(f"Vault already exists at {path}")
    user_password = typer.prompt(
        "Master password", hide_input=True, confirmation_prompt=True
    )
    vault = _get_vault()
    vault.init_db(user_password)
    if ENV_DB_PATH not in os.environ:
        typer.echo(f"No APASS_DB_PATH set, using {path}")
    typer.echo(f"Vault created at {path}")


@app.command()
def create(
    name: t.Annotated[str, typer.Argument(help="Service/utility name")],
    size: t.Annotated[int, typer.Option("--size", "-s", help="Password size")] = generator.DEFAULT_PASSWORD_SIZE,
    min_digits: t.Annotated[int | None, typer.Option("--min-digits", "-d", help="Minimum number of digits")] = None,
    min_special: t.Annotated[int | None, typer.Option("--min-special", "-p", help="Minimum number of special characters")] = None,
) -> None:
    """Create new password and copy it to the clipboard"""
    try:
        service_password = generator.create_password(size=size, min_digits=min_digits, min_special=min_special)
    except ValueError as err:
        _fail(f"Input errors:\n{err}")

    user_password = typer.prompt("Master password", hide_input=True)
    vault = _get_vault()
    try:
        vault.create(name, service_password, user_password)
    except EntryAlreadyExistsError:
        _fail(f"Entry '{name}' already exists. Use the 'set' command to overwrite it.")
    clipboard.copy(service_password)
    typer.echo(f"Password for {name} copied to clipboard")


def _get_vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault(get_db_path())
    return _vault


def _fail(message: str) -> t.NoReturn:
    """Print an error message in red and exit with code 1."""
    typer.secho(message, err=True, fg=typer.colors.RED)
    raise typer.Exit(1)
