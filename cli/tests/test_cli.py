from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from apass.vault import VaultNotInitializedError, WrongPasswordError
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


def test_create_all_params_passed() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.generator.create_password", return_value="abc123") as mock_genetator,
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["create", "example", "-s", "15", "-d", "5", "-p", "2"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.create.assert_called_once_with("example", "abc123", "master123")
    mock_copy.assert_called_once_with("abc123")
    mock_genetator.assert_called_once_with(size=15, min_digits=5, min_special=2)
    assert "Password for example copied to clipboard" in result.output


def test_create_exits_on_value_error() -> None:
    with (
        patch("apass.generator.create_password", side_effect=ValueError("Something went wrong")),
    ):
        result = runner.invoke(app, ["create", "example"], input="master123\n")

    assert result.exit_code == 1
    assert "Something went wrong" in result.output


def test_create_fails_when_vault_not_initialized() -> None:
    mock_vault = MagicMock()
    mock_vault.create.side_effect = VaultNotInitializedError()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["create", "example"], input="master123\n")

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_create_fails_on_wrong_password() -> None:
    mock_vault = MagicMock()
    mock_vault.create.side_effect = WrongPasswordError()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["create", "example"], input="wrongpass\n")

    assert result.exit_code == 1
    assert "Wrong password" in result.output


def test_get_single_match_copies_to_clipboard() -> None:
    mock_entry = MagicMock()
    mock_entry.name = "example"
    mock_entry.password = "s3cret"

    mock_vault = MagicMock()
    mock_vault.search.return_value = [mock_entry]

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["get", "example"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.search.assert_called_once_with("example", "master123")
    mock_copy.assert_called_once_with("s3cret")
    assert "Password for example copied to clipboard" in result.output


def test_get_multiple_matches_prompts_for_choice() -> None:
    mock_entry1 = MagicMock()
    mock_entry1.name = "example.com"
    mock_entry1.password = "pass1"
    mock_entry2 = MagicMock()
    mock_entry2.name = "example.org"
    mock_entry2.password = "pass2"
    mock_entry3 = MagicMock()
    mock_entry3.name = "example.net"
    mock_entry3.password = "pass3"

    mock_vault = MagicMock()
    mock_vault.search.return_value = [mock_entry1, mock_entry2, mock_entry3]

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["get", "example"], input="master123\n2\n")

    assert result.exit_code == 0
    mock_vault.search.assert_called_once_with("example", "master123")
    mock_copy.assert_called_once_with("pass2")
    assert "Found 3 entries matching 'example'" in result.output
    assert "1: example.com" in result.output
    assert "2: example.org" in result.output
    assert "3: example.net" in result.output
    assert "Password for example.org copied to clipboard" in result.output


def test_get_multiple_matches_default_choice() -> None:
    """When user presses Enter without typing a number, default=1 is used."""
    mock_entry1 = MagicMock()
    mock_entry1.name = "foo.com"
    mock_entry1.password = "pass1"
    mock_entry2 = MagicMock()
    mock_entry2.name = "foo.net"
    mock_entry2.password = "pass2"

    mock_vault = MagicMock()
    mock_vault.search.return_value = [mock_entry1, mock_entry2]

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["get", "foo"], input="master123\n\n")

    assert result.exit_code == 0
    mock_copy.assert_called_once_with("pass1")
    assert "Password for foo.com copied to clipboard" in result.output


def test_get_choice_out_of_range_fails() -> None:
    mock_entry1 = MagicMock()
    mock_entry1.name = "x.com"
    mock_entry1.password = "px"
    mock_entry2 = MagicMock()
    mock_entry2.name = "x.org"
    mock_entry2.password = "py"

    mock_vault = MagicMock()
    mock_vault.search.return_value = [mock_entry1, mock_entry2]

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["get", "x"], input="master123\n5\n")

    assert result.exit_code == 1
    assert "Invalid choice" in result.output


def test_get_no_matches_fails() -> None:
    mock_vault = MagicMock()
    mock_vault.search.return_value = []

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["get", "nonexistent"], input="master123\n")

    assert result.exit_code == 1
    assert "No entries found for 'nonexistent'" in result.output


def test_get_fails_when_vault_not_initialized() -> None:
    mock_vault = MagicMock()
    mock_vault.search.side_effect = VaultNotInitializedError()

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["get", "svc"], input="master123\n")

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_get_fails_on_wrong_password() -> None:
    mock_vault = MagicMock()
    mock_vault.search.side_effect = WrongPasswordError()

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["get", "svc"], input="wrongpass\n")

    assert result.exit_code == 1
    assert "Wrong password" in result.output
