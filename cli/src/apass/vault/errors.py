class VaultNotInitializedError(Exception):
    def __init__(self) -> None:
        super().__init__("Vault is not initialized. Run 'apass init' first.")


class EntryAlreadyExistsError(Exception):
    def __init__(self, entry_name: str) -> None:
        super().__init__(f"Entry for {entry_name!r} already exists")


class EntryNotFoundError(Exception):
    def __init__(self, entry_name: str) -> None:
        super().__init__(f"Entry for {entry_name!r} is not found")


class CorruptedVaultError(Exception):
    def __init__(self, message: str = "Vault file is corrupted or has an unsupported format") -> None:
        super().__init__(message)


class WrongPasswordError(Exception):
    def __init__(self) -> None:
        super().__init__("Wrong password or corrupted vault")
