import pytest
from redis.asyncio import Redis

from src.services.cache import RateLimiter, VideoCache
from src.services.users import parse_source

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


async def test_video_cache_roundtrip(redis: Redis) -> None:
    cache = VideoCache(redis, ttl_seconds=3600)
    assert await cache.get(URL) is None

    await cache.set(URL, "file-id-1")
    assert await cache.get(URL) == "file-id-1"
    assert 0 < await redis.ttl(VideoCache.key(URL)) <= 3600

    await cache.delete(URL)
    assert await cache.get(URL) is None


async def test_video_cache_keys_are_stable_and_distinct() -> None:
    assert VideoCache.key(URL) == VideoCache.key(URL)
    assert VideoCache.key(URL) != VideoCache.key(URL + "x")
    assert VideoCache.key(URL).startswith(VideoCache.PREFIX)


async def test_rate_limiter_blocks_after_limit(redis: Redis) -> None:
    limiter = RateLimiter(redis, limit=3, window_seconds=60)
    assert [await limiter.hit(1) for _ in range(3)] == [0, 0, 0]

    retry_after = await limiter.hit(1)
    assert 1 <= retry_after <= 60


async def test_rate_limiter_is_per_user(redis: Redis) -> None:
    limiter = RateLimiter(redis, limit=1, window_seconds=60)
    assert await limiter.hit(1) == 0
    assert await limiter.hit(1) > 0
    assert await limiter.hit(2) == 0


async def test_rate_limiter_sets_expiry(redis: Redis) -> None:
    limiter = RateLimiter(redis, limit=5, window_seconds=60)
    await limiter.hit(42)
    keys = [k async for k in redis.scan_iter(f"{RateLimiter.PREFIX}42:*")]
    assert len(keys) == 1
    assert 0 < await redis.ttl(keys[0]) <= 60


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("src_promo", "promo"),
        ("src_", None),
        ("ref_123", None),
        (None, None),
        ("src_" + "a" * 100, "a" * 64),
    ],
)
def test_parse_source(payload: str | None, expected: str | None) -> None:
    assert parse_source(payload) == expected
