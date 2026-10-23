from collections.abc import AsyncIterator

import pytest
from fakeredis import FakeAsyncRedis
from redis.asyncio import Redis


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()
