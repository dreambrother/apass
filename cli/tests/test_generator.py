import string

from apass import generator
import pytest


def test_create_password_defaults() -> None:
    pw = generator.create_password(size = generator.DEFAULT_PASSWORD_SIZE)
    print(f"Generated password {pw}")
    assert len(pw) == generator.DEFAULT_PASSWORD_SIZE
    assert any(d in pw for d in string.digits)
    assert any(s in pw for s in string.punctuation)


def test_create_password_params() -> None:
    pw = generator.create_password(size=12, min_digits=6, min_special=4)
    print(f"Generated password {pw}")

    assert len(pw) == 12
    assert _count_chars(string.digits, pw) >= 6
    assert _count_chars(string.punctuation, pw) >= 4


def test_create_password_min_digits_eq_size() -> None:
    pw = generator.create_password(size=12, min_digits=12)
    print(f"Generated password {pw}")

    assert _count_chars(string.digits, pw) == 12
    assert _count_chars(string.punctuation, pw) == 0


def test_create_password_min_special_eq_size() -> None:
    pw = generator.create_password(size=12, min_special=12)
    print(f"Generated password {pw}")

    assert _count_chars(string.digits, pw) == 0
    assert _count_chars(string.punctuation, pw) == 12


def test_create_password_lesser_than_min_size() -> None:
    with(pytest.raises(ValueError, match="Password size must be at least")):
        generator.create_password(size=5)


def test_create_password_min_size_gt_password_size() -> None:
    with(pytest.raises(ValueError, match="must be less than or equal to size")):
        generator.create_password(size=10, min_digits=5, min_special=6)


def test_create_password_min_digits_gt_password_size() -> None:
    with(pytest.raises(ValueError, match="must be less than or equal to size")):
        generator.create_password(size=10, min_digits=11)


def test_create_password_min_special_gt_password_size() -> None:
    with(pytest.raises(ValueError, match="must be less than or equal to size")):
        generator.create_password(size=10, min_special=11)


def test_create_password_min_digits_is_negative() -> None:
    with(pytest.raises(ValueError, match="min_digits must be non-negative")):
        generator.create_password(size=10, min_digits=-1)


def test_create_password_min_special_is_negative() -> None:
    with(pytest.raises(ValueError, match="min_special must be non-negative")):
        generator.create_password(size=10, min_special=-1)


def test_create_password_only_min_digits() -> None:
    pw = generator.create_password(size=20, min_digits=10)
    print(f"Generated password {pw}")

    assert len(pw) == 20
    assert _count_chars(string.digits, pw) >= 10
    # min_special is auto-computed when only min_digits is provided
    assert _count_chars(string.punctuation, pw) >= 1


def test_create_password_only_min_special() -> None:
    pw = generator.create_password(size=20, min_special=8)
    print(f"Generated password {pw}")

    assert len(pw) == 20
    assert _count_chars(string.punctuation, pw) >= 8
    # min_digits is auto-computed when only min_special is provided
    assert _count_chars(string.digits, pw) >= 1


def test_create_password_min_digits_plus_min_special_eq_size() -> None:
    pw = generator.create_password(size=10, min_digits=4, min_special=6)
    print(f"Generated password {pw}")

    assert len(pw) == 10
    assert _count_chars(string.digits, pw) == 4
    assert _count_chars(string.punctuation, pw) == 6


def test_create_password_size_eq_min_size() -> None:
    pw = generator.create_password(size=generator.MIN_PASSWORD_SIZE)
    print(f"Generated password {pw}")

    assert len(pw) == generator.MIN_PASSWORD_SIZE
    assert any(d in pw for d in string.digits)
    assert any(s in pw for s in string.punctuation)


def _count_chars(chars: str, pw: str) -> int:
    return sum(c in chars for c in pw)
