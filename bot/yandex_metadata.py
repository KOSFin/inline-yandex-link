from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession

from .models import TrackLink, TrackMetadata

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

STATE_SNAPSHOT_MARKER = "(window.__STATE_SNAPSHOT__ = window.__STATE_SNAPSHOT__ || []).push("
META_TAG_RE = re.compile(r"<meta\s+([^>]+?)>", re.IGNORECASE)
ATTR_RE = re.compile(r'([a-zA-Z:_-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')
JSON_LD_RE = re.compile(
    r'<script[^>]+type=("|\')application/ld\+json\1[^>]*>(?P<body>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
VISIBLE_WHITESPACE_RE = re.compile(r"\s+")
TRACK_DURATION_RE = re.compile(r"Длительность дорожки\s+(\d{1,2}:\d{2})", re.IGNORECASE)
CAPTCHA_MARKERS = (
    "Подтвердите, что запросы отправляли вы, а не робот",
    "Вы не робот?",
    "/checkcaptcha",
    "smartcaptcha",
)


@dataclass
class _CacheEntry:
    metadata: TrackMetadata
    expires_at: float
    touched_at: float


class TrackMetadataClient:
    def __init__(
        self,
        session: ClientSession,
        proxy_url: str | None,
        cache_ttl_seconds: int = 3600,
        cache_size: int = 512,
    ) -> None:
        self._session = session
        self._proxy_url = proxy_url
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache_size = cache_size
        self._cache: dict[str, _CacheEntry] = {}

    async def fetch(self, link: TrackLink) -> TrackMetadata:
        cached = self._cache.get(link.cache_key)
        now = time.monotonic()
        if cached and cached.expires_at > now:
            cached.touched_at = now
            return cached.metadata

        try:
            async with self._session.get(
                link.web_url,
                allow_redirects=True,
                proxy=self._proxy_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                },
            ) as response:
                if response.status != 200:
                    metadata = TrackMetadata(title="ТРЕК", error_code=f"http_{response.status}")
                else:
                    html = await response.text()
                    metadata = extract_track_metadata(html, link)
        except ClientError:
            metadata = TrackMetadata(title="ТРЕК", error_code="network_error")
        except TimeoutError:
            metadata = TrackMetadata(title="ТРЕК", error_code="timeout")

        self._save_to_cache(link.cache_key, metadata, now)
        return metadata

    def _save_to_cache(self, key: str, metadata: TrackMetadata, now: float) -> None:
        self._cache[key] = _CacheEntry(
            metadata=metadata,
            expires_at=now + self._cache_ttl_seconds,
            touched_at=now,
        )

        if len(self._cache) <= self._cache_size:
            return

        oldest_key = min(self._cache.items(), key=lambda item: item[1].touched_at)[0]
        self._cache.pop(oldest_key, None)


def extract_track_metadata(html: str, link: TrackLink) -> TrackMetadata:
    if is_captcha_page(html):
        return TrackMetadata(title="ТРЕК", error_code="captcha_required")

    state_snapshot_metadata = extract_track_metadata_from_state_snapshot(html, link)
    if state_snapshot_metadata is not None:
        return state_snapshot_metadata

    title = extract_meta_content(html, prop="og:title")
    artist = extract_artist(html)
    duration = extract_duration(html, link)

    if not title and not artist and not duration:
        return TrackMetadata(title="ТРЕК", error_code="meta_missing")

    return TrackMetadata(
        title=normalize_visible_text(title) or "ТРЕК",
        artist=normalize_visible_text(artist) or None,
        duration=duration or None,
        error_code=None,
    )


def is_captcha_page(html: str) -> bool:
    return any(marker in html for marker in CAPTCHA_MARKERS)


def extract_track_metadata_from_state_snapshot(html: str, link: TrackLink) -> TrackMetadata | None:
    state_snapshot = extract_state_snapshot(html)
    if not isinstance(state_snapshot, dict):
        return None

    track_state = state_snapshot.get("track")
    if not isinstance(track_state, dict):
        return None

    raw_meta = track_state.get("meta")
    if not isinstance(raw_meta, dict):
        return None

    track_id = str(raw_meta.get("id") or raw_meta.get("realId") or "")
    if track_id != link.track_id:
        return None

    raw_album_id = raw_meta.get("albumId")
    if raw_album_id is not None and str(raw_album_id) != link.album_id:
        return None

    title = normalize_visible_text(raw_meta.get("title"))
    artist = extract_artist_names_from_state_track(raw_meta.get("artists"))
    duration = format_duration_ms(raw_meta.get("durationMs"))

    if not title and not artist and not duration:
        return None

    return TrackMetadata(
        title=title or "ТРЕК",
        artist=artist or None,
        duration=duration or None,
        error_code=None,
    )


def extract_state_snapshot(html: str) -> dict[str, object] | None:
    payload = extract_json_object_after_marker(html, STATE_SNAPSHOT_MARKER)
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def extract_json_object_after_marker(html: str, marker: str) -> str | None:
    marker_start = html.find(marker)
    if marker_start == -1:
        return None

    object_start = html.find("{", marker_start)
    if object_start == -1:
        return None

    depth = 0
    in_string = False
    is_escaped = False

    for index in range(object_start, len(html)):
        char = html[index]

        if in_string:
            if is_escaped:
                is_escaped = False
            elif char == "\\":
                is_escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return html[object_start : index + 1]

    return None


def extract_artist_names_from_state_track(raw_artists: object) -> str | None:
    if not isinstance(raw_artists, list):
        return None

    artist_names = []
    for raw_artist in raw_artists:
        if not isinstance(raw_artist, dict):
            continue
        name = normalize_visible_text(raw_artist.get("name"))
        if name:
            artist_names.append(name)

    if not artist_names:
        return None

    return ", ".join(artist_names)


def extract_meta_content(html: str, *, name: str | None = None, prop: str | None = None) -> str | None:
    for match in META_TAG_RE.finditer(html):
        attrs = parse_tag_attributes(match.group(1))
        if name and attrs.get("name", "").lower() == name.lower():
            return attrs.get("content")
        if prop and attrs.get("property", "").lower() == prop.lower():
            return attrs.get("content")
    return None


def parse_tag_attributes(raw_attributes: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for key, _, double_value, single_value in ATTR_RE.findall(raw_attributes):
        parsed[key.lower()] = double_value or single_value
    return parsed


def extract_artist(html: str) -> str | None:
    og_description = extract_meta_content(html, prop="og:description")
    if not og_description:
        return None

    parts = [normalize_visible_text(part) for part in og_description.split("•")]
    if not parts:
        return None

    artist = parts[0]
    return artist or None


def extract_duration(html: str, link: TrackLink) -> str | None:
    duration = extract_duration_from_json_ld(html, link)
    if duration:
        return duration
    return extract_duration_from_description(html)


def extract_duration_from_description(html: str) -> str | None:
    description = extract_meta_content(html, name="description")
    if not description:
        return None

    match = TRACK_DURATION_RE.search(description)
    if not match:
        return None

    return match.group(1)


def extract_duration_from_json_ld(html: str, link: TrackLink) -> str | None:
    track_suffix = f"/album/{link.album_id}/track/{link.track_id}"

    for match in JSON_LD_RE.finditer(html):
        payload = match.group("body").strip()
        if not payload:
            continue

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue

        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            tracks = item.get("tracks")
            if not isinstance(tracks, list):
                continue
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                if track.get("url") != track_suffix:
                    continue
                return parse_iso_duration(track.get("duration"))

    return None


def parse_iso_duration(value: str | None) -> str | None:
    if not value or not value.startswith("PT"):
        return None

    hours_match = re.search(r"(\d+)H", value)
    minutes_match = re.search(r"(\d+)M", value)
    seconds_match = re.search(r"(\d+)S", value)

    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0

    total_seconds = hours * 3600 + minutes * 60 + seconds
    display_minutes, display_seconds = divmod(total_seconds, 60)
    if hours:
        return f"{hours}:{display_minutes % 60:02d}:{display_seconds:02d}"
    return f"{display_minutes:02d}:{display_seconds:02d}"


def format_duration_ms(value: object) -> str | None:
    try:
        total_seconds = max(int(value), 0) // 1000
    except (TypeError, ValueError):
        return None

    display_minutes, display_seconds = divmod(total_seconds, 60)
    display_hours, display_minutes = divmod(display_minutes, 60)
    if display_hours:
        return f"{display_hours}:{display_minutes:02d}:{display_seconds:02d}"
    return f"{display_minutes:02d}:{display_seconds:02d}"


def normalize_visible_text(value: str | None) -> str:
    if not value:
        return ""
    return VISIBLE_WHITESPACE_RE.sub(" ", value).strip()
