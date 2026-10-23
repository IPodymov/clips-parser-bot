import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from src.bot.handlers import build_router
from src.bot.middlewares import DbSessionMiddleware, UserMiddleware
from src.core.config import get_settings
from src.core.db import create_engine, create_sessionmaker
from src.core.logging import setup_logging
from src.core.redis import create_redis
from src.core.telegram import create_bot
from src.services.cache import RateLimiter, VideoCache
from src.worker.broker import broker

logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать"),
            BotCommand(command="help", description="Как пользоваться"),
        ]
    )


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    redis = create_redis(settings.redis_url)
    bot = create_bot(settings)

    dp = Dispatcher(
        video_cache=VideoCache(redis, ttl_seconds=settings.cache_ttl_days * 86400),
        rate_limiter=RateLimiter(redis, limit=settings.rate_limit_per_minute),
    )
    dp.update.outer_middleware(DbSessionMiddleware(create_sessionmaker(engine)))
    dp.update.outer_middleware(UserMiddleware())
    dp.include_router(build_router())

    await broker.startup()
    try:
        await set_commands(bot)
        logger.info("Bot started (local Bot API: %s)", settings.is_local_bot_api)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await broker.shutdown()
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
