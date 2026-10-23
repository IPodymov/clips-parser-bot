from dataclasses import dataclass

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import ListQueueBroker

from src.core.config import Settings, get_settings
from src.core.db import create_engine, create_sessionmaker
from src.core.logging import setup_logging
from src.core.redis import create_redis
from src.core.telegram import create_bot
from src.downloader.service import VideoDownloader
from src.services.cache import VideoCache

broker = ListQueueBroker(
    get_settings().redis_url,
    queue_name="downloads",
    # BRPOP blocks indefinitely; redis-py's default 5s socket timeout would kill the listener
    socket_timeout=None,
)


@dataclass(slots=True)
class WorkerResources:
    settings: Settings
    bot: Bot
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    cache: VideoCache
    downloader: VideoDownloader


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: TaskiqState) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url)
    redis = create_redis(settings.redis_url)
    state.resources = WorkerResources(
        settings=settings,
        bot=create_bot(settings),
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        redis=redis,
        cache=VideoCache(redis, ttl_seconds=settings.cache_ttl_days * 86400),
        downloader=VideoDownloader(
            download_dir=settings.download_dir,
            max_file_size_bytes=settings.max_file_size_bytes,
            timeout_sec=settings.download_timeout_sec,
            proxy_url=settings.proxy_url,
            cookies_file=settings.ytdlp_cookies_file,
        ),
    )


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: TaskiqState) -> None:
    resources: WorkerResources = state.resources
    await resources.bot.session.close()
    await resources.redis.aclose()
    await resources.engine.dispose()
