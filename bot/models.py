from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class TrackLink:
    album_id: str
    track_id: str
    web_url: str
    app_url: str

    @property
    def cache_key(self) -> str:
        return f"{self.album_id}:{self.track_id}"


@dataclass(frozen=True)
class ArtistLink:
    artist_id: str
    web_url: str
    app_url: str

    @property
    def cache_key(self) -> str:
        return f"artist:{self.artist_id}"


YandexLink = Union[TrackLink, ArtistLink]


@dataclass(frozen=True)
class TrackMetadata:
    title: str
    artist: str | None = None
    duration: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class ArtistMetadata:
    title: str
    likes_count: int | None = None
    last_month_listeners: int | None = None
    error_code: str | None = None


YandexMetadata = Union[TrackMetadata, ArtistMetadata]
