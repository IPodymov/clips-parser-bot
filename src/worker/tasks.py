import html
import logging
from typing import TypedDict

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import FSInputFile, Message
from taskiq import Context, TaskiqDepends

from src.core.models import DownloadStatus
from src.downloader.errors import DownloaderError
from src.downloader.service import DownloadedVideo
from src.services.downloads import record_download
from src.worker.broker import WorkerResources, broker

logger = logging.getLogger(__name__)

GENERIC_ERROR = "❌ Не удалось скачать или отправить видео. Попробуйте позже."
DONE_TEXT = "✅ Готово!"
CAPTION_MAX_LEN = 200


class _JobInfo(TypedDict):
    user_id: int
    url: str
    normalized_url: str
    platform: str


@broker.task(task_name="download_video")
async def download_video(
    chat_id: int,
    status_message_id: int,
    user_id: int,
    url: str,
    normalized_url: str,
    platform: str,
    context: Context = TaskiqDepends(),
) -> None:
    res: WorkerResources = context.state.resources
    record: _JobInfo = {
        "user_id": user_id,
        "url": url,
        "normalized_url": normalized_url,
        "platform": platform,
    }

    # Another task may have finished the same URL while this one was queued
    if cached_file_id := await res.cache.get(normalized_url):
        try:
            await res.bot.send_video(chat_id, video=cached_file_id)
        except TelegramBadRequest:
            logger.warning("Stale cached file_id for %s", normalized_url)
            await res.cache.delete(normalized_url)
        else:
            await _record(res, **record, status=DownloadStatus.SUCCESS, from_cache=True)
            await _edit_status(res, chat_id, status_message_id, DONE_TEXT)
            return

    video: DownloadedVideo | None = None
    try:
        video = await res.downloader.download(url)
        message = await _send_video(res, chat_id, video)
        if file_id := _file_id(message):
            await res.cache.set(normalized_url, file_id)
        await _record(res, **record, status=DownloadStatus.SUCCESS, file_size=video.file_size)
        await _edit_status(res, chat_id, status_message_id, DONE_TEXT)
    except DownloaderError as exc:
        logger.warning("Download failed for %s: %s: %s", url, type(exc).__name__, exc)
        error = f"{type(exc).__name__}: {exc}"
        await _record(res, **record, status=DownloadStatus.FAILED, error=error)
        await _edit_status(res, chat_id, status_message_id, exc.user_message)
    except Exception as exc:
        logger.exception("Unexpected error while processing %s", url)
        error = f"{type(exc).__name__}: {exc}"
        await _record(res, **record, status=DownloadStatus.FAILED, error=error)
        await _edit_status(res, chat_id, status_message_id, GENERIC_ERROR)
    finally:
        if video is not None:
            video.cleanup()


async def _send_video(res: WorkerResources, chat_id: int, video: DownloadedVideo) -> Message:
    # Local Bot API reads the file straight from the shared volume, no HTTP upload
    source: FSInputFile | str = (
        video.path.resolve().as_uri() if res.settings.is_local_bot_api else FSInputFile(video.path)
    )
    caption = html.escape(video.title[:CAPTION_MAX_LEN]) if video.title else None
    return await res.bot.send_video(
        chat_id,
        video=source,
        caption=caption,
        duration=video.duration,
        width=video.width,
        height=video.height,
        supports_streaming=True,
    )


def _file_id(message: Message) -> str | None:
    if message.video:
        return message.video.file_id
    if message.document:
        return message.document.file_id
    return None


async def _edit_status(res: WorkerResources, chat_id: int, message_id: int, text: str) -> None:
    try:
        await res.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as exc:
        # Message deleted by user or text unchanged — not worth failing the task
        logger.debug("Can't edit status message: %s", exc)
    except TelegramAPIError as exc:
        # Bot blocked, chat gone, etc. The download result is already recorded
        logger.warning("Can't edit status message in chat %s: %s", chat_id, exc)


async def _record(
    res: WorkerResources,
    *,
    user_id: int,
    url: str,
    normalized_url: str,
    platform: str,
    status: DownloadStatus,
    file_size: int | None = None,
    error: str | None = None,
    from_cache: bool = False,
) -> None:
    try:
        async with res.sessionmaker() as session:
            await record_download(
                session,
                user_id=user_id,
                url=url,
                normalized_url=normalized_url,
                platform=platform,
                status=status,
                file_size=file_size,
                error=error,
                from_cache=from_cache,
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record download for %s", normalized_url)
