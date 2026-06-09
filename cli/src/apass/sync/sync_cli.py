import typing as t
from contextlib import contextmanager
from datetime import datetime, timezone

import typer

from apass.config import get_db_path
from apass.sync import operations
from apass.sync.backend import CloudApiError, NotLoggedInError
from apass.sync.merge import MergeResult
from apass.sync.state import BackendType, SyncState, load_sync_state, save_sync_state
from apass.vault import Vault, VaultNotInitializedError, WrongPasswordError

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
        provider = operations._PROVIDERS[backend]
    except KeyError:
        _fail(f"Unsupported backend: {backend}")

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
        dt = datetime.fromtimestamp(state.last_sync_at, tz=timezone.utc)
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
        typer.echo("No remote vault found. Run 'apass sync push' to create one.")
        return

    _print_merge_result(result, header="Sync preview (what would happen on push):")


@sync_app.command("push")
def sync_push(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Sync local vault to cloud storage (merge + upload)"""
    vault = Vault(get_db_path())
    provider = operations.get_provider()

    with _sync_error_handler():
        result = operations.perform_push(vault, master_password)

    if result.merge_result:
        _print_merge_result(result.merge_result, header="Merged local and remote vaults.")

    typer.echo(f"\nSynced with {provider.get_display_name()}.")
    typer.echo(f"Remote file ID: {result.remote_file_id}")


@sync_app.command("pull")
def sync_pull(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Sync cloud storage vault to local (merge + download)"""
    vault = Vault(get_db_path())
    provider = operations.get_provider()

    with _sync_error_handler():
        result = operations.perform_pull(vault, master_password)

    _print_merge_result(result, header="Merged remote and local vaults.")
    typer.echo(f"\nSynced with {provider.get_display_name()}.")


@sync_app.command("backend")
def sync_backend(
    backend: t.Annotated[BackendType, typer.Argument(help="Backend to switch to: gdrive or yadisk")],
) -> None:
    """Switch cloud storage backend"""
    try:
        provider = operations._PROVIDERS[backend]
    except KeyError:
        _fail(f"Unsupported backend: {backend}. Use 'gdrive' or 'yadisk'.")

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


def _print_merge_result(result: MergeResult, header: str | None = None) -> None:
    if header:
        typer.echo(header)
    if result.added:
        typer.echo(f"  Added from remote: {', '.join(e.name for e in result.added)}")
    if result.updated:
        typer.echo(f"  Updated: {', '.join(e.name for e in result.updated)}")
    if result.kept_locally_only:
        typer.echo(f"  Kept locally only: {len(result.kept_locally_only)} entries")
    if result.kept_local_with_conflict:
        typer.echo(f"  Kept local (conflict resolved): {len(result.kept_local_with_conflict)} entries")
    typer.echo(f"  Unchanged: {result.unchanged_count} entries")
