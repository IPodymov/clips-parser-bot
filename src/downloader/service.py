import asyncio
import logging
import shutil
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError
from yt_dlp.utils import UnsupportedError

from src.downloader.errors import (
    DownloaderError,
    DownloadFailedError,
    DownloadTimeoutError,
    FileTooLargeError,
    UnsupportedSiteError,
    VideoUnavailableError,
)

logger = logging.getLogger(__name__)

_UNAVAILABLE_MARKERS = (
    "private",
    "login",
    "log in",
    "logged-in",
    "logged in",
    "cookies",
    "sign in",
    "unavailable",
    "not available",
    "removed",
    "deleted",
    "does not exist",
    "age-restricted",
    "members-only",
    "http error 404",
    "http error 403",
)


@dataclass(frozen=True, slots=True)
class DownloadedVideo:
    path: Path
    work_dir: Path
    title: str | None
    duration: int | None
    width: int | None
    height: int | None
    file_size: int

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


class _Cancelled(Exception):
    pass


class VideoDownloader:
    def __init__(
        self,
        download_dir: Path,
        max_file_size_bytes: int,
        timeout_sec: int,
        proxy_url: str | None = None,
        cookies_file: Path | None = None,
    ) -> None:
        self._download_dir = download_dir
        self._max_size = max_file_size_bytes
        self._timeout = timeout_sec
        self._proxy = proxy_url
        self._cookies = cookies_file

    async def download(self, url: str) -> DownloadedVideo:
        """Download a single video. Caller must call `cleanup()` on the result."""
        work_dir = self._download_dir / uuid.uuid4().hex
        work_dir.mkdir(parents=True, exist_ok=True)
        cancel = threading.Event()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._download_sync, url, work_dir, cancel),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            # The thread can't be killed: the progress hook will abort it
            cancel.set()
            shutil.rmtree(work_dir, ignore_errors=True)
            raise DownloadTimeoutError(f"download exceeded {self._timeout}s") from exc
        except BaseException:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    def _ydl_options(self, work_dir: Path, cancel: threading.Event) -> dict[str, Any]:
        max_mb = self._max_size // (1024 * 1024)

        def progress_hook(_: dict[str, Any]) -> None:
            if cancel.is_set():
                raise _Cancelled

        options: dict[str, Any] = {
            # Prefer mp4/h264 + m4a so Telegram can play it inline
            "format": (
                f"bv*[ext=mp4][filesize<?{max_mb}M]+ba[ext=m4a]/"
                f"b[ext=mp4][filesize<?{max_mb}M]/"
                f"bv*[filesize<?{max_mb}M]+ba/b[filesize<?{max_mb}M]/bv*+ba/b"
            ),
            "merge_output_format": "mp4",
            "postprocessor_args": {"merger": ["-movflags", "+faststart"]},
            "outtmpl": str(work_dir / "%(id).64s.%(ext)s"),
            "noplaylist": True,
            "playlist_items": "1",
            "max_filesize": self._max_size,
            "socket_timeout": 30,
            "retries": 3,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [progress_hook],
            "logger": logging.getLogger("yt_dlp"),
        }
        if self._proxy:
            options["proxy"] = self._proxy
        if self._cookies:
            options["cookiefile"] = str(self._cookies)
        return options

    def _download_sync(self, url: str, work_dir: Path, cancel: threading.Event) -> DownloadedVideo:
        try:
            # yt-dlp stubs use strict TypedDicts; we work with plain dicts internally
            options = cast(Any, self._ydl_options(work_dir, cancel))
            with yt_dlp.YoutubeDL(options) as ydl:
                raw = ydl.extract_info(url, download=False)
                info = self._single_entry(cast(dict[str, Any] | None, raw))
                estimated = self._estimated_size(info)
                if estimated and estimated > self._max_size:
                    raise FileTooLargeError(estimated, self._max_size)
                processed = ydl.process_ie_result(cast(Any, info), download=True)
                info = cast(dict[str, Any], processed)
        except DownloaderError:
            raise
        except _Cancelled as exc:
            raise DownloadTimeoutError("cancelled") from exc
        except YtDlpDownloadError as exc:
            raise self._map_error(exc) from exc
        except Exception as exc:
            raise DownloadFailedError(str(exc)) from exc

        path = self._result_path(info, work_dir)
        if path is None:
            # yt-dlp silently skips files above max_filesize
            raise FileTooLargeError(None, self._max_size)
        size = path.stat().st_size
        if size > self._max_size:
            raise FileTooLargeError(size, self._max_size)

        return DownloadedVideo(
            path=path,
            work_dir=work_dir,
            title=info.get("title"),
            duration=_as_int(info.get("duration")),
            width=_as_int(info.get("width")),
            height=_as_int(info.get("height")),
            file_size=size,
        )

    @staticmethod
    def _single_entry(info: dict[str, Any] | None) -> dict[str, Any]:
        if not info:
            raise UnsupportedSiteError("no info extracted")
        if info.get("_type") == "playlist":
            # Carousels / threads: take the first entry
            entries: list[dict[str, Any]] = [e for e in info.get("entries") or [] if e]
            if not entries:
                raise UnsupportedSiteError("empty playlist")
            info = entries[0]
        if info.get("vcodec") == "none" and not info.get("requested_formats"):
            raise UnsupportedSiteError("no video stream")
        return info

    @staticmethod
    def _estimated_size(info: dict[str, Any]) -> int | None:
        formats = info.get("requested_formats") or [info]
        total = 0
        for fmt in formats:
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            if not size:
                return None
            total += int(size)
        return total

    @staticmethod
    def _result_path(info: dict[str, Any], work_dir: Path) -> Path | None:
        for item in info.get("requested_downloads") or []:
            filepath = item.get("filepath")
            if filepath and Path(filepath).exists():
                return Path(filepath)
        files = [p for p in work_dir.iterdir() if p.is_file() and not p.name.endswith(".part")]
        return max(files, key=lambda p: p.stat().st_size, default=None)

    @staticmethod
    def _map_error(exc: YtDlpDownloadError) -> DownloaderError:
        original = exc.exc_info[1] if exc.exc_info else None
        message = str(exc).lower()
        if isinstance(original, UnsupportedError) or "unsupported url" in message:
            return UnsupportedSiteError(str(exc))
        if any(marker in message for marker in _UNAVAILABLE_MARKERS):
            return VideoUnavailableError(str(exc))
        return DownloadFailedError(str(exc))


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
