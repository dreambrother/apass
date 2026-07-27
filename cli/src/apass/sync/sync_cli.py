import typing as t
from contextlib import contextmanager
from datetime import UTC, datetime

import typer

from apass.config import get_db_path
from apass.sync import operations
from apass.sync.backend import CloudApiError, NotLoggedInError
from apass.sync.state import BackendType, SyncState, load_sync_state, save_sync_state
from apass.vault.db import Vault
from apass.vault.errors import VaultNotInitializedError, WrongPasswordError
from apass.vault.merge import MergeResult

sync_app = typer.Typer(help="Sync vault with cloud storage")


@sync_app.command("setup")
def sync_setup(
    backend: t.Annotated[BackendType, typer.Option("--backend", "-b", help="Cloud storage backend")] = "gdrive",
    client_id: t.Annotated[str, typer.Option("--client-id", prompt="OAuth Client ID", hidden=True)] = "",
    client_secret: t.Annotated[str, typer.Option("--client-secret", prompt="OAuth Client Secret", hide_input=True, hidden=True)] = "",
) -> None:
    """Configure OAuth credentials (one-time setup)"""
    if not client_id or not client_secret:
        _fail("Client ID and Client Secret are required")

    try:
        provider = operations.get_provider_for(backend)
    except operations.UnsupportedBackendError as e:
        _fail(str(e))

    provider.save_config(client_id, client_secret)

    state = load_sync_state()
    state.backend = backend
    save_sync_state(state)

    typer.echo(f"{provider.get_display_name()} OAuth credentials saved. Run 'apass sync login' to authorize.")


@sync_app.command("login")
def sync_login() -> None:
    """Authorize apass to access your cloud storage"""
    provider = operations.get_provider()

    if not provider.load_config():
        _fail("OAuth not configured. Run 'apass sync setup' first.")

    try:
        email = provider.run_login_flow()
    except Exception as e:
        _fail(f"Login failed: {e}")

    state = load_sync_state()
    state.account_email = email
    save_sync_state(state)
    typer.echo(f"Logged in as {email}")


@sync_app.command("logout")
def sync_logout() -> None:
    """Remove cloud storage authorization"""
    provider = operations.get_provider()
    provider.delete_credentials()
    save_sync_state(SyncState(backend=load_sync_state().backend))
    typer.echo(f"Logged out from {provider.get_display_name()}")


@sync_app.command("status")
def sync_status() -> None:
    """Show sync status"""
    state = load_sync_state()
    provider = operations.get_provider()

    typer.echo(f"Backend: {provider.get_display_name()}")

    if not provider.is_logged_in():
        typer.echo(f"Not logged in to {provider.get_display_name()}")
        return

    typer.echo(f"Logged in as: {state.account_email or 'unknown'}")
    typer.echo(f"Remote file ID: {state.remote_file_id or 'not synced yet'}")
    if state.last_sync_at:
        dt = datetime.fromtimestamp(state.last_sync_at, tz=UTC)
        typer.echo(f"Last sync: {dt.isoformat()}")
    else:
        typer.echo("Last sync: never")


@sync_app.command("diff")
def sync_diff(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Show what would be synced (dry run)"""
    vault = Vault(get_db_path())

    with _sync_error_handler():
        result = operations.compute_diff(vault, master_password)

    if result is None:
        typer.echo("No remote vault found. Run 'apass sync run' to create one.")
        return

    _print_merge_result(result, header="Sync preview (what would happen on run):")


@sync_app.command("run")
def sync_run(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Bidirectional sync: merge local and remote, write to both"""
    vault = Vault(get_db_path())
    provider = operations.get_provider()

    with _sync_error_handler():
        result = operations.perform_sync(vault, master_password)

    _print_merge_result(result.merge_result, header="Merged local and remote vaults.")
    typer.echo(f"Synced with {provider.get_display_name()}.")
    typer.echo(f"Remote file ID: {result.remote_file_id}")
    if result.backup_path is not None:
        typer.echo(f"Backup saved: {result.backup_path}")


@sync_app.command("backend")
def sync_backend(
    backend: t.Annotated[BackendType, typer.Argument(help="Backend to switch to: gdrive or yadisk")],
) -> None:
    """Switch cloud storage backend"""
    try:
        provider = operations.get_provider_for(backend)
    except operations.UnsupportedBackendError as e:
        _fail(str(e))

    state = load_sync_state()
    state.backend = backend
    save_sync_state(state)

    typer.echo(f"Switched to {provider.get_display_name()}")


@sync_app.command("delete-remote")
def sync_delete_remote(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
    yes: t.Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Permanently delete the remote vault file from cloud storage"""
    provider = operations.get_provider()

    if not yes:
        typer.confirm(
            f"This will PERMANENTLY delete the encrypted vault from {provider.get_display_name()}. Continue?",
            abort=True,
        )

    with _sync_error_handler():
        operations.perform_delete_remote(master_password)

    typer.echo(f"Remote vault deleted from {provider.get_display_name()}.")


def _fail(message: str) -> t.NoReturn:
    """Print an error message in red and exit with code 1."""
    typer.secho(message, err=True, fg=typer.colors.RED)
    raise typer.Exit(1)


@contextmanager
def _sync_error_handler() -> t.Generator[None]:
    try:
        yield
    except NotLoggedInError:
        _fail("Not logged in. Run 'apass sync login' first.")
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")
    except operations.RemoteVaultCorruptedError as e:
        _fail(str(e))
    except operations.NoRemoteVaultError as e:
        _fail(str(e))
    except operations.UnsupportedBackendError as e:
        _fail(str(e))
    except CloudApiError as e:
        _fail(str(e))


def _print_merge_result(result: MergeResult | None, header: str | None = None) -> None:
    if header:
        typer.echo(header)
    if result is None:
        typer.echo("No changes to sync")
        return
    if result.added:
        typer.echo(f"  Added from remote: {', '.join(result.added)}")
    if result.updated:
        typer.echo(f"  Updated: {', '.join(result.updated)}")
    if result.trashed:
        typer.echo(f"  Trashed: {', '.join(result.trashed)}")
    if result.added_to_trash:
        typer.echo(f"  Added to trash: {', '.join(result.added_to_trash)}")
    if result.updated_in_trash:
        typer.echo(f"  Updated in trash: {', '.join(result.updated_in_trash)}")
    if result.restored_from_trash:
        typer.echo(f"  Restored from trash: {', '.join(result.restored_from_trash)}")
