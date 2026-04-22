import asyncio
import logging

from aiohttp import ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from .config import Settings
from .handlers import create_router
from .yandex_metadata import TrackMetadataClient


async def main() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot_session = AiohttpSession(proxy=settings.http_proxy) if settings.http_proxy else AiohttpSession()
    bot = Bot(
        token=settings.bot_token,
        session=bot_session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    timeout = ClientTimeout(total=settings.request_timeout_seconds)

    async with ClientSession(timeout=timeout) as http_session:
        metadata_client = TrackMetadataClient(
            session=http_session,
            proxy_url=settings.http_proxy,
            cache_ttl_seconds=settings.cache_ttl_seconds,
            cache_size=settings.cache_size,
        )

        dispatcher = Dispatcher()
        dispatcher.include_router(create_router(metadata_client))

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

