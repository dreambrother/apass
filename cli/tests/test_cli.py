from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from apass.cli import app

runner = CliRunner()


def test_init_prompts_for_password_and_initializes_db():
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("typer.prompt", return_value="master123"),
    ):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    mock_vault.init_db.assert_called_once_with("master123")
    assert "Vault created at" in result.stdout


def test_create_prompts_for_password_and_stores():
    mock_vault = MagicMock()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
        patch("typer.prompt", return_value="master123"),
    ):
        result = runner.invoke(app, ["create", "example"])

    assert result.exit_code == 0
    mock_vault.create.assert_called_once_with("example", "abc123", "master123")
    mock_copy.assert_called_once_with("abc123")
    assert "Password for example copied to clipboard" in result.output


def test_create_exits_on_value_error():
    with (
        patch("apass.generator.create_password", side_effect=ValueError("Something went wrong")),
        patch("typer.prompt", return_value="master123"),
    ):
        result = runner.invoke(app, ["create", "example"])

    assert result.exit_code == 1
    assert "Something went wrong" in result.output
