from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CopyTextButton,
    InlineQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    MessageEntity,
    Message,
)

from .models import ArtistMetadata, TrackMetadata, YandexLink, YandexMetadata
from .yandex_links import LinkParseError, parse_yandex_link
from .yandex_metadata import TrackMetadataClient

INLINE_TRACK_EMOJI = "🐈"
TRACK_EMOJI = "🎵"
TRACK_CUSTOM_EMOJI_ID = "5472189253121241024"
INLINE_ARTIST_EMOJI = "🎤"
ARTIST_EMOJI = "🎤"


def configure_track_custom_emoji(*, emoji_id: str = TRACK_CUSTOM_EMOJI_ID, emoji: str = TRACK_EMOJI) -> None:
    global TRACK_CUSTOM_EMOJI_ID, TRACK_EMOJI
    TRACK_CUSTOM_EMOJI_ID = emoji_id
    TRACK_EMOJI = emoji


def create_router(
    metadata_client: TrackMetadataClient,
    *,
    app_redirect_base_url: str | None = None,
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer(build_start_message())

    @router.message()
    async def private_message_handler(message: Message) -> None:
        if message.chat.type != "private":
            return

        source_text = (message.text or message.caption or "").strip()
        if not source_text or source_text.startswith("/"):
            return

        try:
            link = parse_yandex_link(source_text)
        except LinkParseError as error:
            await message.answer(build_private_help_message(str(error)))
            return

        metadata = await metadata_client.fetch(link)
        await send_private_track_message(
            message,
            link,
            metadata,
            app_redirect_base_url=app_redirect_base_url,
        )

    @router.inline_query()
    async def inline_query_handler(inline_query: InlineQuery) -> None:
        try:
            link = parse_yandex_link(inline_query.query)
        except LinkParseError as error:
            results = [build_error_result(str(error))]
        else:
            metadata = await metadata_client.fetch(link)
            results = [build_track_result(link, metadata, app_redirect_base_url=app_redirect_base_url)]

        await inline_query.answer(
            results=results,
            cache_time=15,
            is_personal=True,
        )

    return router


def build_track_result(
    link: YandexLink,
    metadata: YandexMetadata,
    *,
    app_redirect_base_url: str | None = None,
) -> InlineQueryResultArticle:
    title = metadata.title or default_title(metadata)
    description = build_result_description(metadata)

    return InlineQueryResultArticle(
        id=link.cache_key,
        title=title,
        description=description,
        input_message_content=build_inline_track_message_content(metadata),
        reply_markup=build_track_reply_markup(link, app_redirect_base_url=app_redirect_base_url),
    )


def build_error_result(error_code: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=f"error:{error_code}",
        title="Нужна ссылка на трек или артиста Яндекс Музыки",
        description="Поддерживаются web и yandexmusic:// ссылки на трек и артиста",
        input_message_content=InputTextMessageContent(
            message_text=(
                f"{INLINE_TRACK_EMOJI} <b>ЯНДЕКС МУЗЫКА</b>\n"
                "Вставь ссылку вида <code>https://music.yandex.ru/album/123/track/456</code>\n"
                "или <code>https://music.yandex.ru/artist/123</code>\n\n"
                f"<code>{escape_html_text(error_code)}</code>"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
    )


def render_message(link: YandexLink, metadata: YandexMetadata) -> str:
    del link
    return render_entity_message(metadata, emoji=emoji_for_private_message(metadata))


def render_inline_message(metadata: YandexMetadata) -> str:
    return render_entity_message(metadata, emoji=emoji_for_inline_message(metadata))


def render_track_message(metadata: TrackMetadata, *, emoji: str) -> str:
    return render_entity_message(metadata, emoji=emoji)


def render_entity_message(metadata: YandexMetadata, *, emoji: str) -> str:
    title = metadata.title or default_title(metadata)
    lines = [f"{emoji} {title}"]

    meta_parts = build_metadata_summary_parts(metadata)
    if meta_parts:
        lines.append(" • ".join(meta_parts))

    if metadata.error_code:
        lines.append("")
        lines.append(metadata.error_code)

    return "\n".join(lines)


def build_inline_track_message_content(metadata: YandexMetadata) -> InputTextMessageContent:
    emoji = emoji_for_inline_message(metadata)
    message_text = render_inline_message(metadata)
    return InputTextMessageContent(
        message_text=message_text,
        entities=build_track_message_entities(metadata, emoji=emoji),
        disable_web_page_preview=True,
    )


def build_track_message_entities(
    metadata: YandexMetadata,
    *,
    emoji: str,
    custom_emoji_id: str | None = None,
) -> list[MessageEntity]:
    title = metadata.title or default_title(metadata)
    entities: list[MessageEntity] = []

    if custom_emoji_id:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=0,
                length=utf16_length(emoji),
                custom_emoji_id=custom_emoji_id,
            )
        )

    entities.append(
        MessageEntity(
            type="bold",
            offset=utf16_length(f"{emoji} "),
            length=utf16_length(title),
        )
    )

    if metadata.error_code:
        prefix = f"{emoji} {title}"
        meta_parts = build_metadata_summary_parts(metadata)
        if meta_parts:
            prefix = f"{prefix}\n{' • '.join(meta_parts)}"
        prefix = f"{prefix}\n\n"
        entities.append(
            MessageEntity(
                type="code",
                offset=utf16_length(prefix),
                length=utf16_length(metadata.error_code),
            )
        )

    return entities


async def send_private_track_message(
    message: Message,
    link: YandexLink,
    metadata: YandexMetadata,
    *,
    app_redirect_base_url: str | None = None,
) -> None:
    emoji = emoji_for_private_message(metadata)
    custom_emoji_id = TRACK_CUSTOM_EMOJI_ID if isinstance(metadata, TrackMetadata) else None
    await message.answer(
        render_message(link, metadata),
        entities=build_track_message_entities(
            metadata,
            emoji=emoji,
            custom_emoji_id=custom_emoji_id,
        ),
        parse_mode=None,
        disable_web_page_preview=True,
        reply_markup=build_track_reply_markup(link, app_redirect_base_url=app_redirect_base_url),
    )


def build_track_reply_markup(
    link: YandexLink,
    *,
    app_redirect_base_url: str | None = None,
) -> InlineKeyboardMarkup:
    app_button = build_app_link_button(link, app_redirect_base_url=app_redirect_base_url)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ОТКРЫТЬ В ВЕБ", url=link.web_url)],
            [app_button],
        ]
    )


def build_app_link_button(
    link: YandexLink,
    *,
    app_redirect_base_url: str | None = None,
) -> InlineKeyboardButton:
    redirect_url = build_redirect_url(link, app_redirect_base_url=app_redirect_base_url)
    if redirect_url:
        return InlineKeyboardButton(text="ОТКРЫТЬ В ПРИЛОЖЕНИИ", url=redirect_url)

    return InlineKeyboardButton(
        text="СКОПИРОВАТЬ APP-ССЫЛКУ",
        copy_text=CopyTextButton(text=link.app_url),
    )


def build_redirect_url(link: YandexLink, *, app_redirect_base_url: str | None = None) -> str | None:
    if not app_redirect_base_url:
        return None

    base_url = app_redirect_base_url.rstrip("/")
    return f"{base_url}/open?{urlencode({'app': link.app_url})}"


def build_start_message() -> str:
    return (
        "Пришли ссылку на трек или артиста Яндекс Музыки сюда или через inline mode.\n\n"
        "Личка:\n"
        "<code>https://music.yandex.ru/album/2448178/track/21404459</code>\n"
        "<code>https://music.yandex.ru/artist/23558757</code>\n\n"
        "Inline:\n"
        "<code>@имя_бота https://music.yandex.ru/album/2448178/track/21404459</code>\n"
        "<code>@имя_бота https://music.yandex.ru/artist/23558757</code>"
    )


def build_private_help_message(error_code: str | None = None) -> str:
    lines = [
        "Пришли ссылку на трек или артиста Яндекс Музыки одним сообщением.",
        "",
        "Поддерживаются:",
        "<code>https://music.yandex.ru/album/123/track/456</code>",
        "<code>yandexmusic://album/123/track/456</code>",
        "<code>https://music.yandex.ru/artist/123</code>",
        "<code>yandexmusic://artist/123</code>",
    ]

    if error_code:
        lines.extend(("", f"<code>{escape_html_text(error_code)}</code>"))

    return "\n".join(lines)


def default_title(metadata: YandexMetadata) -> str:
    if isinstance(metadata, ArtistMetadata):
        return "АРТИСТ"
    return "ТРЕК"


def build_result_description(metadata: YandexMetadata) -> str:
    parts = build_metadata_summary_parts(metadata)
    return " • ".join(parts) or "Преобразовать ссылку Яндекс Музыки"


def build_metadata_summary_parts(metadata: YandexMetadata) -> list[str]:
    if isinstance(metadata, TrackMetadata):
        return [part for part in (metadata.artist, metadata.duration) if part]

    parts: list[str] = []
    if metadata.likes_count is not None:
        parts.append(f"Лайки: {format_count(metadata.likes_count)}")
    if metadata.last_month_listeners is not None:
        parts.append(f"Слушатели/мес: {format_count(metadata.last_month_listeners)}")
    return parts


def emoji_for_inline_message(metadata: YandexMetadata) -> str:
    if isinstance(metadata, ArtistMetadata):
        return INLINE_ARTIST_EMOJI
    return INLINE_TRACK_EMOJI


def emoji_for_private_message(metadata: YandexMetadata) -> str:
    if isinstance(metadata, ArtistMetadata):
        return ARTIST_EMOJI
    return TRACK_EMOJI


def format_count(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def escape_html_text(value: str) -> str:
    return escape(value, quote=False)


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2
