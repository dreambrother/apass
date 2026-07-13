from unittest.mock import MagicMock, patch

from apass.vault.db import PasswordEntry
from typer.testing import CliRunner

from apass.cli import app
from apass.vault.errors import VaultNotInitializedError, WrongPasswordError

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


def test_init_fails_when_password_too_short() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["init"], input="short\nshort\n")

    assert result.exit_code == 1
    assert "Master password is too short" in result.stderr
    assert "at least 8 characters" in result.stderr
    mock_vault.init_db.assert_not_called()


def test_init_warns_when_password_weak() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["init"], input="12345678\n12345678\n")

    assert result.exit_code == 0
    assert "Warning: master password is weak" in result.stderr
    assert "at least 12 characters" in result.stderr
    mock_vault.init_db.assert_called_once_with("12345678")


def test_create_prompts_for_password_and_stores() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["create", "example"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.save.assert_called_once_with("example", "", "abc123", "master123", force=False)
    mock_copy.assert_called_once_with("abc123")
    assert "Password for example copied to clipboard" in result.output


def test_create_all_params_passed() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.generator.create_password", return_value="abc123") as mock_genetator,
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(
            app,
            [
                "create",
                "example",
                "-l", "example_login",
                "-s", "15",
                "-d", "5",
                "-p", "2"
            ],
            input="master123\n"
        )

    assert result.exit_code == 0
    mock_vault.save.assert_called_once_with("example", "example_login", "abc123", "master123", force=False)
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
    mock_vault.save.side_effect = VaultNotInitializedError()
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
    mock_vault.save.side_effect = WrongPasswordError()
    with (
        patch("apass.generator.create_password", return_value="abc123"),
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy"),
    ):
        result = runner.invoke(app, ["create", "example"], input="wrongpass\n")

    assert result.exit_code == 1
    assert "Wrong password" in result.output


def test_get_single_match_copies_to_clipboard() -> None:
    mock_vault = MagicMock()
    mock_vault.search.return_value = [PasswordEntry(name="example", login="", password="s3cret")]

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
    mock_vault = MagicMock()
    mock_vault.search.return_value = [
        PasswordEntry(name="example.com", login="", password="pass1"),
        PasswordEntry(name="example.org", login="user1", password="pass2"),
        PasswordEntry(name="example.net", login="user2", password="pass3"),
    ]

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
    assert "2: example.org/user1" in result.output
    assert "3: example.net/user2" in result.output
    assert "Password for example.org/user1 copied to clipboard" in result.output


def test_get_multiple_matches_default_choice() -> None:
    """When user presses Enter without typing a number, default=1 is used."""
    entries = [
        PasswordEntry(name="foo.com", password="pass1", login=""),
        PasswordEntry(name="foo.net", password="pass2", login=""),
    ]

    mock_vault = MagicMock()
    mock_vault.search.return_value = entries

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
        patch("apass.clipboard.copy") as mock_copy,
    ):
        result = runner.invoke(app, ["get", "foo"], input="master123\n\n")

    assert result.exit_code == 0
    mock_copy.assert_called_once_with("pass1")
    assert "Password for foo.com copied to clipboard" in result.output


def test_get_choice_out_of_range_fails() -> None:
    entries = [
        PasswordEntry(name="x.com", password="px", login=""),
        PasswordEntry(name="x.org", password="py", login=""),
    ]

    mock_vault = MagicMock()
    mock_vault.search.return_value = entries

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


def test_save_prompts_for_passwords_and_stores() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["save", "example"], input="master123\nservice123\n")

    assert result.exit_code == 0
    mock_vault.save.assert_called_once_with("example", "", "service123", "master123", False)
    assert "Password for example set successfully" in result.output


def test_save_with_login_prompts_for_passwords_and_stores_force() -> None:
    mock_vault = MagicMock()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["save", "example", "-l", "test_login", "--force"], input="master123\nservice123\n")

    assert result.exit_code == 0
    mock_vault.save.assert_called_once_with("example", "test_login", "service123", "master123", True)
    assert "Password for example/test_login set successfully" in result.output


def test_save_fails_when_vault_not_initialized() -> None:
    mock_vault = MagicMock()
    mock_vault.save.side_effect = VaultNotInitializedError()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["save", "example"], input="master123\nservice123\n")

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_save_fails_on_wrong_password() -> None:
    mock_vault = MagicMock()
    mock_vault.save.side_effect = WrongPasswordError()
    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["save", "example"], input="master123\nservice123\n")

    assert result.exit_code == 1
    assert "Wrong password" in result.output


def test_remove_single_match() -> None:
    entries = [PasswordEntry(name="example", password="s3cret", login="")]

    mock_vault = MagicMock()
    mock_vault.search.return_value = entries

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["remove", "example"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.remove.assert_called_once_with("example", "", "master123")
    assert "Recycle Bin" in result.output
    assert "Password for example moved to Recycle Bin" in result.output


def test_remove_multiple_matches_prompts_for_choice() -> None:
    entries = [
        PasswordEntry(name="example.com", password="pass1", login="user1"),
        PasswordEntry(name="example.org", password="pass2", login=""),
        PasswordEntry(name="example.org", password="pass3", login="user3"),
    ]

    mock_vault = MagicMock()
    mock_vault.search.return_value = entries

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["remove", "example"], input="master123\n3\n")

    assert result.exit_code == 0
    mock_vault.remove.assert_called_once_with("example.org", "user3", "master123")
    assert "Found 3 entries matching 'example'" in result.output
    assert "1: example.com/user1" in result.output
    assert "2: example.org" in result.output
    assert "3: example.org/user3" in result.output
    assert "Password for example.org moved to Recycle Bin" in result.output


def test_remove_multiple_matches_default_choice() -> None:
    """When user presses Enter without typing a number, default=1 is used."""
    entries = [
        PasswordEntry(name="foo.com", password="pass1", login=""),
        PasswordEntry(name="foo.net", password="pass2", login=""),
    ]

    mock_vault = MagicMock()
    mock_vault.search.return_value = entries

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["remove", "foo"], input="master123\n\n")

    assert result.exit_code == 0
    assert "Password for foo.com moved to Recycle Bin" in result.output


def test_restore_single_match() -> None:
    from apass.vault.db import PasswordEntry

    mock_entry = PasswordEntry(name="example", login="u", password="s3cret")

    mock_vault = MagicMock()
    mock_vault.list_trashed.return_value = [mock_entry]

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["restore", "example"], input="master123\n")

    assert result.exit_code == 0
    mock_vault.list_trashed.assert_called_once_with("example", "master123")
    mock_vault.restore.assert_called_once_with("example", "u", "master123")
    assert "Password for example restored from Recycle Bin" in result.output


def test_restore_no_matches() -> None:
    mock_vault = MagicMock()
    mock_vault.list_trashed.return_value = []

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["restore", "missing"], input="master123\n")

    assert result.exit_code == 1
    assert "No trashed entries found" in result.output


def test_restore_fails_when_vault_not_initialized() -> None:
    mock_vault = MagicMock()
    mock_vault.list_trashed.side_effect = VaultNotInitializedError()

    with (
        patch("apass.cli._get_vault", return_value=mock_vault),
    ):
        result = runner.invoke(app, ["restore", "x"], input="master123\n")

    assert result.exit_code == 1
    assert "not initialized" in result.output
