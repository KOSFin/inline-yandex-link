from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    http_proxy: str | None
    log_level: str
    request_timeout_seconds: float
    cache_ttl_seconds: int
    cache_size: int

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is required")

        http_proxy = first_non_empty(
            os.getenv("HTTP_PROXY"),
            os.getenv("http_proxy"),
            os.getenv("HTTPS_PROXY"),
            os.getenv("https_proxy"),
        )

        return cls(
            bot_token=bot_token,
            http_proxy=http_proxy,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            cache_size=int(os.getenv("CACHE_SIZE", "512")),
        )


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None
