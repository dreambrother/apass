from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from apass.cli import app

runner = CliRunner()


def test_init_prompts_for_password_and_initializes_db() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["init"], input="master123\nmaster123\n")

    assert result.exit_code == 0
    mock_vault.init_db.assert_called_once_with("master123")
    assert "Vault created at" in result.stdout


def test_create_prompts_for_password_and_stores() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["create", "example"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.create.assert_called_once_with("example", "abc123", "master123")
    mock_copy.assert_called_once_with("abc123")
    assert "Password for example copied to clipboard" in result.output


def test_create_exits_on_value_error() -> None:
    with (
        patch("apass.generator.create_password", side_effect=ValueError("Something went wrong")),
    ):
        result = runner.invoke(app, ["create", "example"], input="master123\n")

    assert result.exit_code == 1
    assert "Something went wrong" in result.output
