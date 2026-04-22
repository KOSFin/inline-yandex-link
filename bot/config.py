from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    telegram_proxy: str | None
    metadata_proxy: str | None
    app_redirect_base_url: str | None
    log_level: str
    request_timeout_seconds: float
    cache_ttl_seconds: int
    cache_size: int

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is required")

        default_proxy = first_non_empty(
            os.getenv("HTTP_PROXY"),
            os.getenv("http_proxy"),
            os.getenv("HTTPS_PROXY"),
            os.getenv("https_proxy"),
        )
        telegram_proxy = proxy_from_env("TELEGRAM_PROXY", fallback=default_proxy)
        metadata_proxy = proxy_from_env("METADATA_PROXY", fallback=default_proxy)

        return cls(
            bot_token=bot_token,
            telegram_proxy=telegram_proxy,
            metadata_proxy=metadata_proxy,
            app_redirect_base_url=normalize_base_url(os.getenv("APP_REDIRECT_BASE_URL")),
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


def proxy_from_env(name: str, *, fallback: str | None = None) -> str | None:
    if name not in os.environ:
        return fallback

    value = os.getenv(name, "").strip()
    if value.lower() in {"", "none", "direct", "off"}:
        return None

    return value


def normalize_base_url(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().rstrip("/")
    return normalized or None
