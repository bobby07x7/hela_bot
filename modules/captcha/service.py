from __future__ import annotations

import json
import random

from core.cache import redis

PENDING_KEY_PREFIX = "captcha:pending"


def generate_challenge(rng: random.Random | None = None) -> tuple[str, str]:
    """Pure: returns (question, answer). Simple addition, easy for a human,
    tedious for a dumb join-bot."""
    rng = rng or random
    a = rng.randint(1, 20)
    b = rng.randint(1, 20)
    return f"{a} + {b} = ?", str(a + b)


def _pending_key(chat_id: int, user_id: int) -> str:
    return f"{PENDING_KEY_PREFIX}:{chat_id}:{user_id}"


async def set_pending(chat_id: int, user_id: int, answer: str, name: str, ttl_seconds: int) -> None:
    payload = json.dumps({"answer": answer, "name": name})
    await redis.set(_pending_key(chat_id, user_id), payload, ex=ttl_seconds)


async def get_pending(chat_id: int, user_id: int) -> dict | None:
    raw = await redis.get(_pending_key(chat_id, user_id))
    if raw is None:
        return None
    return json.loads(raw)


async def clear_pending(chat_id: int, user_id: int) -> None:
    await redis.delete(_pending_key(chat_id, user_id))


def check_answer(pending: dict, submitted: str) -> bool:
    """Pure: whether the submitted text matches the stored answer."""
    return submitted.strip() == pending.get("answer", "").strip()
