from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User

DAILY_COOLDOWN = dt.timedelta(hours=24)


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None = None,
                              first_name: str | None = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.flush()
    else:
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            await session.flush()
    return user


def format_timedelta(delta: dt.timedelta) -> str:
    total = int(delta.total_seconds())
    if total <= 0:
        return "0s"
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not hours:
        parts.append(f"{seconds}s")
    return " ".join(parts)


async def claim_daily(session: AsyncSession, user: User, reward_min: int, reward_max: int) -> tuple[bool, int, dt.timedelta]:
    """Returns (claimed, amount_or_0, time_remaining_if_not_claimed)."""
    now = dt.datetime.now(dt.timezone.utc)
    if user.last_daily_at is not None:
        elapsed = now - user.last_daily_at
        if elapsed < DAILY_COOLDOWN:
            return False, 0, DAILY_COOLDOWN - elapsed

        # Streak survives if claimed within 48h of the last claim.
        if elapsed < DAILY_COOLDOWN * 2:
            user.daily_streak += 1
        else:
            user.daily_streak = 1
    else:
        user.daily_streak = 1

    amount = random.randint(reward_min, reward_max) + (user.daily_streak - 1) * 5
    user.balance += amount
    user.last_daily_at = now
    await session.flush()
    return True, amount, dt.timedelta(0)


async def do_work(session: AsyncSession, user: User, reward_min: int, reward_max: int,
                   cooldown_seconds: int) -> tuple[bool, int, dt.timedelta]:
    now = dt.datetime.now(dt.timezone.utc)
    if user.last_work_at is not None:
        elapsed = now - user.last_work_at
        remaining = dt.timedelta(seconds=cooldown_seconds) - elapsed
        if remaining.total_seconds() > 0:
            return False, 0, remaining

    amount = random.randint(reward_min, reward_max)
    user.balance += amount
    user.last_work_at = now
    await session.flush()
    return True, amount, dt.timedelta(0)


async def transfer(session: AsyncSession, sender: User, recipient: User, amount: int) -> bool:
    if amount <= 0 or sender.balance < amount:
        return False
    sender.balance -= amount
    recipient.balance += amount
    await session.flush()
    return True


async def top_balances(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(select(User).order_by(User.balance.desc()).limit(limit))
    return list(result.scalars())
