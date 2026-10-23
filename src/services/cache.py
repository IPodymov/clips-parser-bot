import hashlib
import time

from redis.asyncio import Redis


class VideoCache:
    """Maps normalized URL → Telegram file_id of an already uploaded video."""

    PREFIX = "video:"

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @classmethod
    def key(cls, normalized_url: str) -> str:
        digest = hashlib.sha1(normalized_url.encode(), usedforsecurity=False).hexdigest()
        return cls.PREFIX + digest

    async def get(self, normalized_url: str) -> str | None:
        value = await self._redis.get(self.key(normalized_url))
        return str(value) if value is not None else None

    async def set(self, normalized_url: str, file_id: str) -> None:
        await self._redis.set(self.key(normalized_url), file_id, ex=self._ttl)

    async def delete(self, normalized_url: str) -> None:
        await self._redis.delete(self.key(normalized_url))


class RateLimiter:
    """Fixed-window limiter: at most `limit` hits per `window` seconds per user."""

    PREFIX = "rl:"

    def __init__(self, redis: Redis, limit: int, window_seconds: int = 60) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    async def hit(self, user_id: int) -> int:
        """Register a hit. Returns 0 if allowed, otherwise seconds to wait."""
        window_start = int(time.time()) // self._window
        key = f"{self.PREFIX}{user_id}:{window_start}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, self._window, nx=True)
            count, _ = await pipe.execute()
        if int(count) <= self._limit:
            return 0
        return max(1, (window_start + 1) * self._window - int(time.time()))
