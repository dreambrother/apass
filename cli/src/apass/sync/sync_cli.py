import typing as t
from contextlib import contextmanager
from datetime import datetime, timezone

import typer

from apass.config import get_db_path
from apass.sync import operations
from apass.sync.gdrive import DriveApiError
from apass.sync.merge import MergeResult
from apass.sync.oauth import (
    OAuthConfig,
    delete_credentials,
    get_user_email,
    load_credentials,
    load_oauth_config,
    run_login_flow,
    save_oauth_config,
)
from apass.sync.state import SyncState, load_sync_state, save_sync_state
from apass.vault import Vault, VaultNotInitializedError, WrongPasswordError

sync_app = typer.Typer(help="Sync vault with Google Drive")


@sync_app.command("setup")
def sync_setup(
    client_id: t.Annotated[str, typer.Option(prompt="Google OAuth Client ID", hidden=True)],
    client_secret: t.Annotated[str, typer.Option(prompt="Google OAuth Client Secret", hide_input=True, hidden=True)],
) -> None:
    """Configure Google Drive OAuth credentials (one-time setup)"""
    config = OAuthConfig(client_id=client_id, client_secret=client_secret)
    save_oauth_config(config)
    typer.echo("OAuth credentials saved. Run 'apass sync login' to authorize.")


@sync_app.command("login")
def sync_login() -> None:
    """Authorize apass to access your Google Drive"""
    config = load_oauth_config()
    if not config:
        _fail("OAuth not configured. Run 'apass sync setup' first.")

    try:
        creds = run_login_flow(config)
        email = get_user_email(creds)
    except Exception as e:
        _fail(f"Login failed: {e}")

    state = SyncState(account_email=email)
    save_sync_state(state)
    typer.echo(f"Logged in as {email}")


@sync_app.command("logout")
def sync_logout() -> None:
    """Remove Google Drive authorization"""
    delete_credentials()
    save_sync_state(SyncState())
    typer.echo("Logged out from Google Drive")


@sync_app.command("status")
def sync_status() -> None:
    """Show sync status"""
    state = load_sync_state()
    creds = load_credentials()

    if not creds:
        typer.echo("Not logged in to Google Drive")
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
    """Sync local vault to Google Drive (merge + upload)"""
    vault = Vault(get_db_path())

    with _sync_error_handler():
        result = operations.perform_push(vault, master_password)

    if result.merge_result:
        _print_merge_result(result.merge_result, header="Merged local and remote vaults.")

    typer.echo("\nSynced with Google Drive.")
    typer.echo(f"Remote file ID: {result.remote_file_id}")


@sync_app.command("pull")
def sync_pull(
    master_password: t.Annotated[str, typer.Option(prompt="Master password", hide_input=True, hidden=True)],
) -> None:
    """Sync Google Drive vault to local (merge + download)"""
    vault = Vault(get_db_path())

    with _sync_error_handler():
        result = operations.perform_pull(vault, master_password)

    _print_merge_result(result, header="Merged remote and local vaults.")
    typer.echo("\nSynced with Google Drive.")


def _fail(message: str) -> t.NoReturn:
    """Print an error message in red and exit with code 1."""
    typer.secho(message, err=True, fg=typer.colors.RED)
    raise typer.Exit(1)


@contextmanager
def _sync_error_handler() -> t.Generator[None]:
    try:
        yield
    except operations.NotLoggedInError:
        _fail("Not logged in. Run 'apass sync login' first.")
    except VaultNotInitializedError:
        _fail("Vault is not initialized. Run 'apass init' first.")
    except WrongPasswordError:
        _fail("Wrong password")
    except operations.RemoteVaultCorruptedError as e:
        _fail(str(e))
    except operations.NoRemoteVaultError as e:
        _fail(str(e))
    except DriveApiError as e:
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
