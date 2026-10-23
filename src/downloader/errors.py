class DownloaderError(Exception):
    """Base downloader error. `user_message` is safe to show in the chat."""

    user_message = "❌ Не удалось скачать видео. Попробуйте позже."


class UnsupportedSiteError(DownloaderError):
    user_message = "🚫 Этот сайт не поддерживается или по ссылке нет видео."


class VideoUnavailableError(DownloaderError):
    user_message = "🔒 Видео недоступно: оно приватное, удалено или требует входа в аккаунт."


class FileTooLargeError(DownloaderError):
    def __init__(self, size_bytes: int | None, limit_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(f"file size {size_bytes} exceeds limit {limit_bytes}")

    @property
    def user_message(self) -> str:  # type: ignore[override]
        limit_mb = self.limit_bytes // (1024 * 1024)
        return f"📦 Видео слишком большое. Максимальный размер — {limit_mb} МБ."


class DownloadTimeoutError(DownloaderError):
    user_message = "⌛ Скачивание заняло слишком много времени. Попробуйте позже."


class DownloadFailedError(DownloaderError):
    pass
