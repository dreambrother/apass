import os


vault_dir = os.path.expanduser("~/.apass")
os.makedirs(vault_dir, exist_ok=True)
vault_file = os.path.join(vault_dir, "vault")


def store(service_name: str, service_password: str, user_password: str) -> None:
    pass
