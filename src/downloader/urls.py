"""URL extraction, platform detection and normalization.

Normalized URL is used as the cache key, so different links to the same
video (youtu.be / shorts / watch, tracking params, mobile hosts) must map
to the same string.
"""

import re
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

TRACKING_PARAMS = frozenset(
    {
        "si",
        "feature",
        "igsh",
        "igshid",
        "fbclid",
        "gclid",
        "yclid",
        "ref",
        "ref_src",
        "ref_url",
        "share_id",
        "_r",
        "_t",
    }
)
TRACKING_PREFIXES = ("utm_",)

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class Platform(StrEnum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    VK = "vk"
    X = "x"
    OTHER = "other"


_PLATFORM_HOSTS: dict[Platform, tuple[str, ...]] = {
    Platform.YOUTUBE: ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    Platform.TIKTOK: ("tiktok.com",),
    Platform.INSTAGRAM: ("instagram.com", "instagr.am"),
    Platform.VK: ("vk.com", "vk.ru", "vkvideo.ru"),
    Platform.X: ("x.com", "twitter.com"),
}

_STRIP_HOST_PREFIXES = ("www.", "m.", "mobile.")


def extract_url(text: str | None) -> str | None:
    """Return the first http(s) URL found in text."""
    if not text:
        return None
    match = URL_RE.search(text)
    if match is None:
        return None
    return match.group(0).rstrip(".,!?;:)]}»")


def _bare_host(host: str) -> str:
    host = host.lower().split(":", 1)[0]
    for prefix in _STRIP_HOST_PREFIXES:
        if host.startswith(prefix):
            return host[len(prefix) :]
    return host


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def detect_platform(url: str) -> Platform:
    host = _bare_host(urlsplit(url).netloc)
    for platform, domains in _PLATFORM_HOSTS.items():
        if any(_host_matches(host, domain) for domain in domains):
            return platform
    return Platform.OTHER


def _is_tracking(param: str) -> bool:
    return param.lower() in TRACKING_PARAMS or param.lower().startswith(TRACKING_PREFIXES)


def _youtube_video_id(host: str, path: str, query: dict[str, str]) -> str | None:
    if host == "youtu.be":
        candidate = path.strip("/").split("/", 1)[0]
    elif "v" in query:
        candidate = query["v"]
    else:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v", "e"}:
            candidate = parts[1]
        else:
            return None
    return candidate if YOUTUBE_ID_RE.match(candidate) else None


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = "https"
    host = _bare_host(parts.netloc)
    path = parts.path.rstrip("/") or "/"
    query_pairs = parse_qsl(parts.query, keep_blank_values=False)
    platform = detect_platform(url)

    if platform is Platform.YOUTUBE:
        video_id = _youtube_video_id(host, parts.path, dict(query_pairs))
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        host = "youtube.com"

    if platform in (Platform.TIKTOK, Platform.INSTAGRAM, Platform.X):
        # Path fully identifies the media; query string is only tracking
        if platform is Platform.X:
            host = "x.com"
        return urlunsplit((scheme, host, path, "", ""))

    kept = sorted((k, v) for k, v in query_pairs if not _is_tracking(k))
    return urlunsplit((scheme, host, path, urlencode(kept), ""))
