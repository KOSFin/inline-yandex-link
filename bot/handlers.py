from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

from .models import TrackLink, TrackMetadata
from .yandex_links import LinkParseError, parse_track_link
from .yandex_metadata import TrackMetadataClient


def create_router(metadata_client: TrackMetadataClient) -> Router:
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
            results = [build_track_result(link, metadata)]

        await inline_query.answer(
            results=results,
            cache_time=15,
            is_personal=True,
        )

    return router


def build_track_result(link: TrackLink, metadata: TrackMetadata) -> InlineQueryResultArticle:
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
    )


def build_error_result(error_code: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=f"error:{error_code}",
        title="Нужна ссылка на трек Яндекс Музыки",
        description="Поддерживаются web и yandexmusic:// ссылки на трек",
        input_message_content=InputTextMessageContent(
            message_text=(
                "🎵 <b>ТРЕК</b>\n"
                "Вставь ссылку вида <code>https://music.yandex.ru/album/123/track/456</code>\n\n"
                f"<code>{escape(error_code)}</code>"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
    )


def render_message(link: TrackLink, metadata: TrackMetadata) -> str:
    title = escape(metadata.title or "ТРЕК")
    lines = [f"🎵 <b>{title}</b>"]

    meta_parts = [escape(part) for part in (metadata.artist, metadata.duration) if part]
    if meta_parts:
        lines.append(" • ".join(meta_parts))

    lines.append("")
    lines.append(f'<a href="{escape(link.web_url)}">ОТКРЫТЬ В ВЕБ</a>')
    lines.append(f'<a href="{escape(link.app_url)}">ОТКРЫТЬ В ПРИЛОЖЕНИИ</a>')

    if metadata.error_code:
        lines.append("")
        lines.append(f"<code>{escape(metadata.error_code)}</code>")

    return "\n".join(lines)

