import logging

from aiogram import F, Router
from aiogram.enums import MessageEntityType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DownloadStatus, User
from src.downloader.urls import detect_platform, extract_url, normalize_url
from src.services.cache import RateLimiter, VideoCache
from src.services.downloads import record_download
from src.worker.tasks import download_video

logger = logging.getLogger(__name__)
router = Router(name="links")

NO_LINK_TEXT = "Пришлите ссылку на видео, например: https://youtu.be/…"
QUEUE_ERROR_TEXT = "❌ Сервис временно недоступен. Попробуйте через минуту."


def _message_url(message: Message) -> str | None:
    # Hidden links (text_link entities) take priority over plain text
    for entity in message.entities or []:
        if entity.type == MessageEntityType.TEXT_LINK and entity.url:
            return entity.url
    return extract_url(message.text)


@router.message(F.text)
async def handle_link(
    message: Message,
    user: User,
    session: AsyncSession,
    video_cache: VideoCache,
    rate_limiter: RateLimiter,
) -> None:
    url = _message_url(message)
    if url is None:
        await message.answer(NO_LINK_TEXT)
        return

    if retry_after := await rate_limiter.hit(user.tg_id):
        await message.answer(f"🐢 Слишком много ссылок. Подождите {retry_after} сек.")
        return

    normalized = normalize_url(url)
    platform = detect_platform(url)

    if file_id := await video_cache.get(normalized):
        try:
            await message.reply_video(file_id)
        except TelegramBadRequest:
            logger.warning("Stale cached file_id for %s, re-downloading", normalized)
            await video_cache.delete(normalized)
        else:
            await record_download(
                session,
                user_id=user.id,
                url=url,
                normalized_url=normalized,
                platform=platform,
                status=DownloadStatus.SUCCESS,
                from_cache=True,
            )
            return

    status = await message.reply("⏳ Загружаю…")
    try:
        await download_video.kiq(
            chat_id=message.chat.id,
            status_message_id=status.message_id,
            user_id=user.id,
            url=url,
            normalized_url=normalized,
            platform=platform,
        )
    except Exception:
        logger.exception("Failed to enqueue download for %s", url)
        await status.edit_text(QUEUE_ERROR_TEXT)
