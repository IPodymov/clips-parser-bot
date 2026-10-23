from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Download, DownloadStatus


async def record_download(
    session: AsyncSession,
    *,
    user_id: int,
    url: str,
    normalized_url: str,
    platform: str,
    status: DownloadStatus,
    file_size: int | None = None,
    error: str | None = None,
    from_cache: bool = False,
) -> Download:
    download = Download(
        user_id=user_id,
        url=url,
        normalized_url=normalized_url,
        platform=platform,
        status=status,
        file_size=file_size,
        error=error[:2000] if error else None,
        from_cache=from_cache,
    )
    session.add(download)
    await session.flush()
    return download
