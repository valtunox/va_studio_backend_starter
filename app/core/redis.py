"""
Redis Configuration

Async Redis client for caching and session management.
"""

import json
from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.settings import settings


class RedisClient:
    """Async Redis client wrapper with caching utilities."""

    def __init__(self):
        self._client: Optional[Redis] = None
        self._prefix = settings.REDIS_PREFIX
        self._default_ttl = settings.REDIS_TTL

    async def connect(self) -> None:
        """Initialize Redis connection."""
        self._client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if not self._client:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.client.get(self._key(key))

    async def set(
        self,
        key: str,
        value: Union[str, int, float],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value with optional TTL."""
        return await self.client.set(
            self._key(key),
            value,
            ex=ttl or self._default_ttl,
        )

    async def delete(self, key: str) -> int:
        """Delete key."""
        return await self.client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(self._key(key)) > 0

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value by key."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set JSON value with optional TTL."""
        return await self.set(key, json.dumps(value), ttl)

    async def incr(self, key: str) -> int:
        """Increment value."""
        return await self.client.incr(self._key(key))

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key."""
        return await self.client.expire(self._key(key), ttl)

    async def ttl(self, key: str) -> int:
        """Get remaining TTL."""
        return await self.client.ttl(self._key(key))

    # Session management
    async def set_session(
        self,
        session_id: str,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Store session data."""
        return await self.set_json(f"session:{session_id}", data, ttl)

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data."""
        return await self.get_json(f"session:{session_id}")

    async def delete_session(self, session_id: str) -> int:
        """Delete session."""
        return await self.delete(f"session:{session_id}")

    # Rate limiting
    async def rate_limit_check(
        self,
        identifier: str,
        max_requests: int,
        window: int,
    ) -> tuple[bool, int]:
        """
        Check rate limit for identifier.

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        key = f"ratelimit:{identifier}"
        current = await self.client.incr(self._key(key))

        if current == 1:
            await self.expire(key, window)

        remaining = max(0, max_requests - current)
        is_allowed = current <= max_requests

        return is_allowed, remaining

    # Cache decorator helpers
    async def cache_get_or_set(
        self,
        key: str,
        factory,
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Get cached value or compute and cache it.

        Args:
            key: Cache key
            factory: Async function to compute value if not cached
            ttl: Time to live in seconds
        """
        cached = await self.get_json(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set_json(key, value, ttl)
        return value


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency for getting Redis client."""
    return redis_client
