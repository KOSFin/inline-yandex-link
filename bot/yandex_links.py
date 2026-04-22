from __future__ import annotations

import re
from dataclasses import dataclass

from .models import TrackLink

YANDEX_WEB_BASE = "https://music.yandex.ru"
YANDEX_APP_BASE = "yandexmusic://"

WEB_TRACK_RE = re.compile(
    r"""
    (?P<full>
        (?:
            https?://
        )?
        music\.yandex\.(?:ru|com|kz|by|uz)
        /(?:[a-z]{2}/)?
        album/(?P<album_id>\d+)
        /track/(?P<track_id>\d+)
        (?:[/?#][^\s]*)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

APP_TRACK_RE = re.compile(
    r"""
    (?P<full>
        yandexmusic://
        album/(?P<album_id>\d+)
        /track/(?P<track_id>\d+)
        (?:[/?#][^\s]*)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class LinkParseError(ValueError):
    code: str

    def __str__(self) -> str:
        return self.code


def parse_track_link(query: str) -> TrackLink:
    source = query.strip()
    if not source:
        raise LinkParseError("empty_query")

    for pattern in (WEB_TRACK_RE, APP_TRACK_RE):
        match = pattern.search(source)
        if match:
            album_id = match.group("album_id")
            track_id = match.group("track_id")
            return TrackLink(
                album_id=album_id,
                track_id=track_id,
                web_url=f"{YANDEX_WEB_BASE}/album/{album_id}/track/{track_id}",
                app_url=f"{YANDEX_APP_BASE}album/{album_id}/track/{track_id}",
            )

    raise LinkParseError("unsupported_link")
