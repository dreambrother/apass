import random
import string


MIN_PASSWORD_SIZE = 6
DEFAULT_PASSWORD_SIZE = 16


# TODO no digits, no specials
def create_password(
    size: int,
    min_digits: int | None = None,
    min_special: int | None = None
) -> str:
    _validate(size, min_digits, min_special)

    if min_digits is not None and min_special is not None:
        pass
    elif min_digits is not None:
        min_special = min(size // 6, size - min_digits)
    elif min_special is not None:
        min_digits = min(size // 6, size - min_special)
    else:
        min_digits = size // 6
        min_special = size // 6

    chars_remain = size

    digits_count = _random_count(min_digits, chars_remain - min_special, size)
    chars_remain -= digits_count

    special_count = _random_count(min_special, chars_remain, size)
    chars_remain -= special_count

    letters_count = chars_remain

    characters = (
        random.choices(string.ascii_letters, k=letters_count)
        + random.choices(string.digits, k=digits_count)
        + random.choices(string.punctuation, k=special_count)
    )
    random.shuffle(characters)
    return ''.join(characters)


def _validate(
    size: int,
    min_digits: int | None,
    min_special: int | None
) -> None:
    error_messages = []
    if size < MIN_PASSWORD_SIZE:
        error_messages.append(f"Password size must be at least {MIN_PASSWORD_SIZE}")
    if min_digits is not None and min_digits < 0:
        error_messages.append("min_digits must be non-negative")
    if min_special is not None and min_special < 0:
        error_messages.append("min_special must be non-negative")
    if (min_digits or 0) + (min_special or 0) > size:
        error_messages.append("min_digits + min_special must be less than or equal to size")
    if error_messages:
        raise ValueError("\n".join(error_messages))


def _random_count(min_count: int, chars_remain: int, password_size: int) -> int:
    if chars_remain <= min_count:
        return chars_remain
    upper_bound = min(max(min_count, password_size // 3), chars_remain)
    return random.randint(min_count, upper_bound)
