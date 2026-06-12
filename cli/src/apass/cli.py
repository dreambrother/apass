import os
import typing as t

import typer

from apass import clipboard, generator
from apass.config import ENV_DB_PATH, get_db_path
from apass.sync.sync_cli import sync_app
from apass.vault import EntryAlreadyExistsError, PasswordEntry, VaultNotInitializedError, WrongPasswordError, Vault

app = typer.Typer()
app.add_typer(sync_app, name="sync")


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """APass — password manager."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def init(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, confirmation_prompt=True, hidden=True)],
) -> None:
    if len(master_password) < 8:
        _fail(
            "Master password is too short. "
            "It must be at least 8 characters; "
            "12 or more is recommended for adequate security."
        )
    if len(master_password) < 12:
        typer.secho(
            "Warning: master password is weak. "
            "Consider using at least 12 characters for better security.",
            err=True,
            fg=typer.colors.YELLOW,
        )

    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _fail(f"Vault already exists at {path}")
    vault = _get_vault()
    vault.init_db(master_password)
    if ENV_DB_PATH not in os.environ:
        typer.echo(f"No APASS_DB_PATH set, using {path}")
    typer.echo(f"Vault created at {path}")


@app.command()
def create(
    name: t.Annotated[str, typer.Argument(help="Service/utility name")],
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
    size: t.Annotated[int, typer.Option("--size", "-s", help="Password size")] = generator.DEFAULT_PASSWORD_SIZE,
    min_digits: t.Annotated[int | None, typer.Option("--min-digits", "-d", help="Minimum number of digits (0 to disable)")] = None,
    min_special: t.Annotated[int | None, typer.Option("--min-special", "-p", help="Minimum number of special characters (0 to disable)")] = None,
    login: t.Annotated[str | None, typer.Option("--login", "-l", help="Service/utility login")] = None,
) -> None:
    """Create new password and copy it to the clipboard"""
    try:
        service_password = generator.create_password(size=size, min_digits=min_digits, min_special=min_special)
    except ValueError as err:
        _fail(f"Input errors:\n{err}")

    vault = _get_vault()
    try:
        vault.save(name, service_password, master_password, login, force=False)
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")
    except EntryAlreadyExistsError:
        _fail(f"Entry '{name}' already exists. Use the 'save' command with --force to overwrite it.")
    clipboard.copy(service_password)
    typer.echo(f"Password for {name} copied to clipboard")


@app.command()
def get(
    name: t.Annotated[str, typer.Argument(help="Service/utility name")],
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Search for a password by name and copy it to the clipboard"""
    vault = _get_vault()
    try:
        entries = vault.search(name, master_password)
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")

    if not entries:
        _fail(f"No entries found for '{name}'")

    if len(entries) == 1:
        entry = entries[0]
    else:
        entry = _ask_user_choice(name, entries)

    clipboard.copy(entry.password)
    typer.echo(f"Password for {entry.name} copied to clipboard")


@app.command()
def save(
    name: t.Annotated[str, typer.Argument(help="Service/utility name")],
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
    service_password: t.Annotated[str, typer.Option(prompt="Service password", hide_input=True, hidden=True)],
    login: t.Annotated[str | None, typer.Option("--login", "-l", help="Service/utility login")] = None,
    force: t.Annotated[bool, typer.Option("-f", "--force", help="Overwrite existing value")] = False,
) -> None:
    """Save existing password"""
    vault = _get_vault()
    try:
        vault.save(name, service_password, master_password, login, force)
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")
    except EntryAlreadyExistsError:
        _fail(f"Entry '{name}' already exists. Use --force to overwrite it.")
    typer.echo(f"Password for {name} set successfully")


@app.command()
def remove(
    name: t.Annotated[str, typer.Argument(help="Service/utility name")],
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
    yes: t.Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Remove a password by name"""
    vault = _get_vault()
    try:
        entries = vault.search(name, master_password)
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")

    if not entries:
        _fail(f"No entries found for '{name}'")

    if len(entries) == 1:
        entry = entries[0]
    else:
        entry = _ask_user_choice(name, entries)

    if not yes:
        typer.confirm(
            f"This will PERMANENTLY remove the {entry.name} password from vault. Continue?",
            abort=True,
        )
    vault.remove(entry.name, master_password)

    typer.echo(f"Password for {entry.name} is removed")


def _get_vault() -> Vault:
    return Vault(get_db_path())


def _fail(message: str) -> t.NoReturn:
    """Print an error message in red and exit with code 1."""
    typer.secho(message, err=True, fg=typer.colors.RED)
    raise typer.Exit(1)


def _ask_user_choice(name: str, entries: list[PasswordEntry]) -> PasswordEntry:
    typer.echo(f"Found {len(entries)} entries matching '{name}':\n")
    for i, entry in enumerate(entries, start=1):
        typer.echo(f"  {i}: {entry.name}")
    typer.echo()
    choice = typer.prompt("Choose entry number", type=int, default=1)
    if choice < 1 or choice > len(entries):
        _fail(f"Invalid choice: {choice}. Must be between 1 and {len(entries)}.")
    return entries[choice - 1]
