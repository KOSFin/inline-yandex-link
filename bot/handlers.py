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
    Message,
)

from .models import TrackLink, TrackMetadata
from .yandex_links import LinkParseError, parse_track_link
from .yandex_metadata import TrackMetadataClient

TRACK_EMOJI_HTML = '<tg-emoji emoji-id="5472189253121241024"></tg-emoji>'


def create_router(
    metadata_client: TrackMetadataClient,
    *,
    app_redirect_base_url: str | None = None,
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer(
            (
                "Пришли ссылку через inline mode.\n"
                "Пример: `@имя_бота https://music.yandex.ru/album/2448178/track/21404459`"
            )
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
        input_message_content=InputTextMessageContent(
            message_text=render_message(link, metadata),
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
        reply_markup=build_track_reply_markup(link, app_redirect_base_url=app_redirect_base_url),
    )


def build_error_result(error_code: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=f"error:{error_code}",
        title="Нужна ссылка на трек Яндекс Музыки",
        description="Поддерживаются web и yandexmusic:// ссылки на трек",
        input_message_content=InputTextMessageContent(
            message_text=(
                f"{TRACK_EMOJI_HTML} <b>ТРЕК</b>\n"
                "Вставь ссылку вида <code>https://music.yandex.ru/album/123/track/456</code>\n\n"
                f"<code>{escape_html_text(error_code)}</code>"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
    )


def render_message(link: TrackLink, metadata: TrackMetadata) -> str:
    title = escape_html_text(metadata.title or "ТРЕК")
    lines = [f"{TRACK_EMOJI_HTML} <b>{title}</b>"]

    meta_parts = [escape_html_text(part) for part in (metadata.artist, metadata.duration) if part]
    if meta_parts:
        lines.append(" • ".join(meta_parts))

    if metadata.error_code:
        lines.append("")
        lines.append(f"<code>{escape_html_text(metadata.error_code)}</code>")

    return "\n".join(lines)


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


def escape_html_text(value: str) -> str:
    return escape(value, quote=False)
