"""Redis cache helper."""
from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

import redis.asyncio as aioredis

from app.config import settings

T = TypeVar("T")

_cache: aioredis.Redis | None = None


def get_cache() -> aioredis.Redis:
    global _cache
    if _cache is None:
        _cache = aioredis.from_url(
            settings.REDIS_CACHE_URL, encoding="utf-8", decode_responses=True
        )
    return _cache


async def cache_get(key: str) -> Any | None:
    client = get_cache()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    client = get_cache()
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    client = get_cache()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern."""
    client = get_cache()
    keys = await client.keys(pattern)
    if keys:
        await client.delete(*keys)


def cache_key(*parts: str) -> str:
    return ":".join(parts)
