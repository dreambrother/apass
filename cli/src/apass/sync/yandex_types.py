from dataclasses import dataclass


@dataclass
class YandexToken:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
