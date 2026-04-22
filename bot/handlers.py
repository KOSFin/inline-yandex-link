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

from .models import TrackLink, TrackMetadata
from .yandex_links import LinkParseError, parse_track_link
from .yandex_metadata import TrackMetadataClient

INLINE_TRACK_EMOJI = "🐈"
TRACK_EMOJI = "🎵"
TRACK_CUSTOM_EMOJI_ID = "5472189253121241024"


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
            link = parse_track_link(source_text)
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
            link = parse_track_link(inline_query.query)
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
    link: TrackLink,
    metadata: TrackMetadata,
    *,
    app_redirect_base_url: str | None = None,
) -> InlineQueryResultArticle:
    title = metadata.title or "ТРЕК"
    description_parts = [part for part in (metadata.artist, metadata.duration) if part]
    description = " • ".join(description_parts) or "Преобразовать ссылку Яндекс Музыки"

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
        title="Нужна ссылка на трек Яндекс Музыки",
        description="Поддерживаются web и yandexmusic:// ссылки на трек",
        input_message_content=InputTextMessageContent(
            message_text=(
                f"{INLINE_TRACK_EMOJI} <b>ТРЕК</b>\n"
                "Вставь ссылку вида <code>https://music.yandex.ru/album/123/track/456</code>\n\n"
                f"<code>{escape_html_text(error_code)}</code>"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
    )


def render_message(link: TrackLink, metadata: TrackMetadata) -> str:
    del link
    return render_track_message(metadata, emoji=TRACK_EMOJI)


def render_inline_message(metadata: TrackMetadata) -> str:
    return render_track_message(metadata, emoji=INLINE_TRACK_EMOJI)


def render_track_message(metadata: TrackMetadata, *, emoji: str) -> str:
    title = metadata.title or "ТРЕК"
    lines = [f"{emoji} {title}"]

    meta_parts = [part for part in (metadata.artist, metadata.duration) if part]
    if meta_parts:
        lines.append(" • ".join(meta_parts))

    if metadata.error_code:
        lines.append("")
        lines.append(metadata.error_code)

    return "\n".join(lines)


def build_inline_track_message_content(metadata: TrackMetadata) -> InputTextMessageContent:
    message_text = render_inline_message(metadata)
    return InputTextMessageContent(
        message_text=message_text,
        entities=build_track_message_entities(metadata, emoji=INLINE_TRACK_EMOJI),
        disable_web_page_preview=True,
    )


def build_track_message_entities(
    metadata: TrackMetadata,
    *,
    emoji: str,
    custom_emoji_id: str | None = None,
) -> list[MessageEntity]:
    title = metadata.title or "ТРЕК"
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
        meta_parts = [part for part in (metadata.artist, metadata.duration) if part]
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
    link: TrackLink,
    metadata: TrackMetadata,
    *,
    app_redirect_base_url: str | None = None,
) -> None:
    await message.answer(
        render_message(link, metadata),
        entities=build_track_message_entities(
            metadata,
            emoji=TRACK_EMOJI,
            custom_emoji_id=TRACK_CUSTOM_EMOJI_ID,
        ),
        parse_mode=None,
        disable_web_page_preview=True,
        reply_markup=build_track_reply_markup(link, app_redirect_base_url=app_redirect_base_url),
    )


def build_track_reply_markup(
    link: TrackLink,
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
    link: TrackLink,
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


def build_redirect_url(link: TrackLink, *, app_redirect_base_url: str | None = None) -> str | None:
    if not app_redirect_base_url:
        return None

    base_url = app_redirect_base_url.rstrip("/")
    return f"{base_url}/open?{urlencode({'app': link.app_url})}"


def build_start_message() -> str:
    return (
        "Пришли ссылку на трек Яндекс Музыки сюда или через inline mode.\n\n"
        "Личка:\n"
        "<code>https://music.yandex.ru/album/2448178/track/21404459</code>\n\n"
        "Inline:\n"
        "<code>@имя_бота https://music.yandex.ru/album/2448178/track/21404459</code>"
    )


def build_private_help_message(error_code: str | None = None) -> str:
    lines = [
        "Пришли ссылку на трек Яндекс Музыки одним сообщением.",
        "",
        "Поддерживаются:",
        "<code>https://music.yandex.ru/album/123/track/456</code>",
        "<code>yandexmusic://album/123/track/456</code>",
    ]

    if error_code:
        lines.extend(("", f"<code>{escape_html_text(error_code)}</code>"))

    return "\n".join(lines)


def escape_html_text(value: str) -> str:
    return escape(value, quote=False)


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2
