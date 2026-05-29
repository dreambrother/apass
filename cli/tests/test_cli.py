from pytest_mock import MockerFixture

from apass.cli import create


def test_create_prompts_for_password_and_stores(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("apass.generator.create_password", return_value="abc123")
    mock_prompt = mocker.patch("typer.prompt", return_value="master123")
    mock_store = mocker.patch("apass.vault.store")
    mock_copy = mocker.patch("apass.clipboard.copy")

    create("example")

    mock_create.assert_called_once()
    mock_prompt.assert_called_once_with("Master password", hide_input=True)
    mock_store.assert_called_once_with("example", "abc123", "master123")
    mock_copy.assert_called_once_with("abc123")
