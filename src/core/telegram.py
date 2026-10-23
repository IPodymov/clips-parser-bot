from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from src.core.config import Settings


def create_bot(settings: Settings) -> Bot:
    """Bot instance shared by the bot process and the worker."""
    session = None
    if settings.bot_api_url:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.bot_api_url, is_local=True),
            # Large uploads to the local server may take a while
            timeout=settings.download_timeout_sec,
        )
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
