from __future__ import annotations

from dataclasses import dataclass


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
class TrackMetadata:
    title: str
    artist: str | None = None
    duration: str | None = None
    error_code: str | None = None
