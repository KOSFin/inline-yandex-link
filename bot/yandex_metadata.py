from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from html import unescape

from aiohttp import ClientError, ClientSession

from .models import ArtistLink, ArtistMetadata, TrackLink, TrackMetadata, YandexLink, YandexMetadata

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
ARTIST_LISTENERS_RE = re.compile(
    r"(?P<count>[\d\s\xa0]+)\s+слушател(?:ь|я|ей)\s+в\s+месяц",
    re.IGNORECASE,
)
PAGE_HEADING_RE = re.compile(r"<h1[^>]*>(?P<body>.*?)</h1>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
PRELOADED_ARTIST_LIKES_RE = re.compile(
    r'\\"preloadedArtist\\":\{\\"artist\\":\{\\"id\\":\\"(?P<artist_id>\d+)\\".*?\\"likesCount\\":(?P<likes_count>\d+)',
    re.DOTALL,
)
CAPTCHA_MARKERS = (
    "Подтвердите, что запросы отправляли вы, а не робот",
    "Вы не робот?",
    "/checkcaptcha",
    "smartcaptcha",
)


@dataclass
class _CacheEntry:
    metadata: YandexMetadata
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

    async def fetch(self, link: YandexLink) -> YandexMetadata:
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
                    metadata = build_error_metadata(link, f"http_{response.status}")
                else:
                    html = await response.text()
                    metadata = extract_metadata(html, link)
        except ClientError:
            metadata = build_error_metadata(link, "network_error")
        except TimeoutError:
            metadata = build_error_metadata(link, "timeout")

        if metadata.error_code is None:
            self._save_to_cache(link.cache_key, metadata, now)
        return metadata

    def _save_to_cache(self, key: str, metadata: YandexMetadata, now: float) -> None:
        self._cache[key] = _CacheEntry(
            metadata=metadata,
            expires_at=now + self._cache_ttl_seconds,
            touched_at=now,
        )

        if len(self._cache) <= self._cache_size:
            return

        oldest_key = min(self._cache.items(), key=lambda item: item[1].touched_at)[0]
        self._cache.pop(oldest_key, None)


def build_error_metadata(link: YandexLink, error_code: str) -> YandexMetadata:
    if isinstance(link, ArtistLink):
        return ArtistMetadata(title="АРТИСТ", error_code=error_code)
    return TrackMetadata(title="ТРЕК", error_code=error_code)


def extract_metadata(html: str, link: YandexLink) -> YandexMetadata:
    if isinstance(link, ArtistLink):
        return extract_artist_metadata(html, link)
    return extract_track_metadata(html, link)


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


def extract_artist_metadata(html: str, link: ArtistLink) -> ArtistMetadata:
    if is_captcha_page(html):
        return ArtistMetadata(title="АРТИСТ", error_code="captcha_required")

    title: str | None = None
    last_month_listeners: int | None = None

    state_snapshot_metadata = extract_artist_metadata_from_state_snapshot(html, link)
    if state_snapshot_metadata is not None:
        title = state_snapshot_metadata.title
        last_month_listeners = state_snapshot_metadata.last_month_listeners

    if not title:
        title = extract_artist_name_from_heading(html)

    if last_month_listeners is None:
        last_month_listeners = extract_artist_last_month_listeners_from_html(html)

    likes_count = extract_artist_likes_count_from_preloaded_artist(html, link)

    if not title and likes_count is None and last_month_listeners is None:
        return ArtistMetadata(title="АРТИСТ", error_code="meta_missing")

    return ArtistMetadata(
        title=title or "АРТИСТ",
        likes_count=likes_count,
        last_month_listeners=last_month_listeners,
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


def extract_artist_metadata_from_state_snapshot(html: str, link: ArtistLink) -> ArtistMetadata | None:
    state_snapshot = extract_state_snapshot(html)
    if not isinstance(state_snapshot, dict):
        return None

    artist_state = state_snapshot.get("artist")
    if not isinstance(artist_state, dict):
        return None

    raw_meta = artist_state.get("meta")
    if not isinstance(raw_meta, dict):
        return None

    raw_artist = raw_meta.get("artist")
    if not isinstance(raw_artist, dict):
        return None

    artist_id = str(raw_artist.get("id") or artist_state.get("id") or "")
    if artist_id != link.artist_id:
        return None

    title = normalize_visible_text(raw_artist.get("name"))
    last_month_listeners = parse_int_value(raw_meta.get("lastMonthListeners"))

    if not title and last_month_listeners is None:
        return None

    return ArtistMetadata(
        title=title or "АРТИСТ",
        likes_count=None,
        last_month_listeners=last_month_listeners,
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


def extract_artist_name_from_heading(html: str) -> str | None:
    match = PAGE_HEADING_RE.search(html)
    if not match:
        return None

    heading = HTML_TAG_RE.sub(" ", match.group("body"))
    return normalize_visible_text(heading) or None


def extract_artist_last_month_listeners_from_html(html: str) -> int | None:
    match = ARTIST_LISTENERS_RE.search(unescape(html))
    if not match:
        return None

    return parse_human_number(match.group("count"))


def extract_artist_likes_count_from_preloaded_artist(html: str, link: ArtistLink) -> int | None:
    for match in PRELOADED_ARTIST_LIKES_RE.finditer(html):
        if match.group("artist_id") != link.artist_id:
            continue
        return parse_human_number(match.group("likes_count"))

    return None


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


def parse_int_value(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_human_number(value: str | None) -> int | None:
    if not value:
        return None

    digits = re.sub(r"\D", "", value)
    if not digits:
        return None

    return int(digits)


def normalize_visible_text(value: str | None) -> str:
    if not value:
        return ""
    return VISIBLE_WHITESPACE_RE.sub(" ", unescape(value)).strip()
