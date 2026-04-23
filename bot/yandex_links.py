from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ArtistLink, TrackLink, YandexLink

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

WEB_ARTIST_RE = re.compile(
    r"""
    (?P<full>
        (?:
            https?://
        )?
        music\.yandex\.(?:ru|com|kz|by|uz)
        /(?:[a-z]{2}/)?
        artist/(?P<artist_id>\d+)
        (?:[/?#][^\s]*)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

APP_ARTIST_RE = re.compile(
    r"""
    (?P<full>
        yandexmusic://
        artist/(?P<artist_id>\d+)
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

    link = _match_track_link(source)
    if link:
        return link

    raise LinkParseError("unsupported_link")


def parse_artist_link(query: str) -> ArtistLink:
    source = query.strip()
    if not source:
        raise LinkParseError("empty_query")

    link = _match_artist_link(source)
    if link:
        return link

    raise LinkParseError("unsupported_link")


def parse_yandex_link(query: str) -> YandexLink:
    source = query.strip()
    if not source:
        raise LinkParseError("empty_query")

    for matcher in (_match_track_link, _match_artist_link):
        link = matcher(source)
        if link:
            return link

    raise LinkParseError("unsupported_link")


def _match_track_link(source: str) -> TrackLink | None:
    for pattern in (WEB_TRACK_RE, APP_TRACK_RE):
        match = pattern.search(source)
        if not match:
            continue

        album_id = match.group("album_id")
        track_id = match.group("track_id")
        return TrackLink(
            album_id=album_id,
            track_id=track_id,
            web_url=f"{YANDEX_WEB_BASE}/album/{album_id}/track/{track_id}",
            app_url=f"{YANDEX_APP_BASE}album/{album_id}/track/{track_id}",
        )

    return None


def _match_artist_link(source: str) -> ArtistLink | None:
    for pattern in (WEB_ARTIST_RE, APP_ARTIST_RE):
        match = pattern.search(source)
        if not match:
            continue

        artist_id = match.group("artist_id")
        return ArtistLink(
            artist_id=artist_id,
            web_url=f"{YANDEX_WEB_BASE}/artist/{artist_id}",
            app_url=f"{YANDEX_APP_BASE}artist/{artist_id}",
        )

    return None
