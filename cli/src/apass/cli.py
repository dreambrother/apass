import typing as t

from apass import clipboard, generator, vault
import typer

app = typer.Typer()


@app.callback()
def callback():
    """APass — password manager."""


@app.command()
def create(name: t.Annotated[str, typer.Argument(help="Your name")]) -> None:
    """Create new password and copy it to the clipboard"""
    service_password = generator.create_password()
    user_password = typer.prompt("Master password", hide_input=True)
    vault.store(name, service_password, user_password)
    clipboard.copy(service_password)


if __name__ == "__main__":
    app()
