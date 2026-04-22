import asyncio
import logging

from aiohttp import ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from .config import Settings
from .handlers import TRACK_CUSTOM_EMOJI_ID, TRACK_EMOJI, configure_track_custom_emoji, create_router
from .yandex_metadata import TrackMetadataClient


async def resolve_track_custom_emoji(bot: Bot) -> str:
    try:
        stickers = await bot.get_custom_emoji_stickers(custom_emoji_ids=[TRACK_CUSTOM_EMOJI_ID])
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to resolve custom emoji %s, falling back to %s",
            TRACK_CUSTOM_EMOJI_ID,
            TRACK_EMOJI,
            exc_info=True,
        )
        return TRACK_EMOJI

    if not stickers:
        return TRACK_EMOJI

    emoji = (stickers[0].emoji or "").strip()
    return emoji or TRACK_EMOJI


async def main() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot_session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else AiohttpSession()
    bot = Bot(
        token=settings.bot_token,
        session=bot_session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    configure_track_custom_emoji(emoji=await resolve_track_custom_emoji(bot))
    timeout = ClientTimeout(total=settings.request_timeout_seconds)

    async with ClientSession(timeout=timeout) as http_session:
        metadata_client = TrackMetadataClient(
            session=http_session,
            proxy_url=settings.metadata_proxy,
            cache_ttl_seconds=settings.cache_ttl_seconds,
            cache_size=settings.cache_size,
        )

        dispatcher = Dispatcher()
        dispatcher.include_router(
            create_router(
                metadata_client,
                app_redirect_base_url=settings.app_redirect_base_url,
            )
        )

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
