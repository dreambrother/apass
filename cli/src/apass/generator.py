import random
import string


def create_password() -> str:
    characters = string.ascii_letters + string.digits
    # Randomly choose characters and merge them into a single string
    return ''.join(random.choices(characters, k=10))
