import json
import warnings
from typing import Any

import redis
from axiom.cache.client import RedisClient

from app.core.config import get_settings

settings = get_settings()

redis_client: RedisClient | None = None

if settings.redis_url:
    try:
        probe = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        try:
            probe.ping()
        finally:
            probe.close()
        redis_client = RedisClient(settings.redis_url)
    except Exception as e:
        warnings.warn(f"Redis disabled — invalid REDIS_URL: {e}", stacklevel=1)


class CacheService:
    TTL_SHORT = 120    # 2 min  — mutable lists (api-key list)
    TTL_DEFAULT = 300  # 5 min  — profiles, resolved entities

    def __init__(self, redis: RedisClient):
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: Any, ttl: int = TTL_DEFAULT):
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, *keys: str):
        if keys:
            await self._redis.delete(*keys)


class CacheKeys:
    """Single source of truth for every cache key pattern in the app."""

    @staticmethod
    def user(uid: str) -> str:
        return f"user:{uid}"

    @staticmethod
    def apikey(hashed: str) -> str:
        return f"apikey:{hashed}"

    @staticmethod
    def user_apikeys(owner_uid: str) -> str:
        return f"user_apikeys:{owner_uid}"


def get_cache() -> CacheService | None:
    """FastAPI dependency — returns None when Redis is not configured."""
    if redis_client is None:
        return None
    return CacheService(redis_client)


def set_cache_header(response: Any, hit: bool) -> None:
    """Stamps X-Cache: HIT or MISS on the response."""
    response.headers["X-Cache"] = "HIT" if hit else "MISS"