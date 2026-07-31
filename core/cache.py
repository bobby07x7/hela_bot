from __future__ import annotations

from redis import asyncio as aioredis

from core.config import get_settings

_settings = get_settings()
redis = aioredis.from_url(_settings.redis_url, decode_responses=True)


async def check_cooldown(key: str, seconds: int) -> int:
    """Returns 0 if the action is allowed (and starts the cooldown),
    otherwise the number of seconds still remaining."""
    ttl = await redis.ttl(key)
    if ttl and ttl > 0:
        return ttl
    await redis.set(key, "1", ex=seconds)
    return 0


async def clear_cooldown(key: str) -> None:
    await redis.delete(key)


async def ping() -> bool:
    try:
        return bool(await redis.ping())
    except Exception:
        return False
