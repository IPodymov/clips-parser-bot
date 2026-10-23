import pytest

from src.downloader.urls import Platform, detect_platform, extract_url, normalize_url

YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("смотри https://youtu.be/dQw4w9WgXcQ !", "https://youtu.be/dQw4w9WgXcQ"),
        ("(https://vk.com/video-1_2).", "https://vk.com/video-1_2"),
        ("http://x.com/a/status/1", "http://x.com/a/status/1"),
        ("без ссылки", None),
        ("", None),
        (None, None),
    ],
)
def test_extract_url(text: str | None, expected: str | None) -> None:
    assert extract_url(text) == expected


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        (YT, Platform.YOUTUBE),
        ("https://youtu.be/dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://m.youtube.com/shorts/dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://www.tiktok.com/@user/video/123", Platform.TIKTOK),
        ("https://vm.tiktok.com/ZMabc/", Platform.TIKTOK),
        ("https://www.instagram.com/reel/Cabc/", Platform.INSTAGRAM),
        ("https://vk.com/video-1_2", Platform.VK),
        ("https://vkvideo.ru/video-1_2", Platform.VK),
        ("https://twitter.com/u/status/1", Platform.X),
        ("https://x.com/u/status/1", Platform.X),
        ("https://vimeo.com/123", Platform.OTHER),
        ("https://notyoutube.com/watch?v=dQw4w9WgXcQ", Platform.OTHER),
    ],
)
def test_detect_platform(url: str, platform: Platform) -> None:
    assert detect_platform(url) is platform


@pytest.mark.parametrize(
    "url",
    [
        YT,
        "https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share&si=abc",
        "http://m.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ&t=42",
        "https://youtu.be/dQw4w9WgXcQ?si=tracking",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "https://youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ?si=x",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_normalize_youtube_variants_collapse(url: str) -> None:
    assert normalize_url(url) == YT


def test_normalize_youtube_without_video_id_keeps_path() -> None:
    assert normalize_url("https://www.youtube.com/@channel?si=x") == "https://youtube.com/@channel"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.tiktok.com/@user/video/123?is_from_webapp=1&sender_device=pc",
            "https://tiktok.com/@user/video/123",
        ),
        (
            "https://www.instagram.com/reel/Cabc123/?igsh=MTIz&utm_source=ig",
            "https://instagram.com/reel/Cabc123",
        ),
        ("https://twitter.com/user/status/1?s=20&t=abc", "https://x.com/user/status/1"),
        ("https://mobile.twitter.com/user/status/1", "https://x.com/user/status/1"),
    ],
)
def test_normalize_drops_query_for_path_based_platforms(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_normalize_generic_strips_tracking_and_sorts_params() -> None:
    url = "HTTP://WWW.Example.com/v/1/?utm_source=tg&b=2&a=1&fbclid=x#frag"
    assert normalize_url(url) == "https://example.com/v/1?a=1&b=2"


def test_normalize_vk_keeps_meaningful_params() -> None:
    url = "https://m.vk.com/wall-1_2?z=video-1_2&utm_medium=share"
    assert normalize_url(url) == "https://vk.com/wall-1_2?z=video-1_2"


def test_normalize_is_idempotent() -> None:
    for url in (YT, "https://x.com/u/status/1", "https://example.com/v?a=1"):
        assert normalize_url(normalize_url(url)) == normalize_url(url)
