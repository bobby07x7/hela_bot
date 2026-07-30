from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from core.logging import get_logger
from database.models import User
from database.session import get_session

logger = get_logger(__name__)


async def expire_premium_job() -> None:
    """Runs periodically: downgrades any user whose premium_until has passed."""
    now = dt.datetime.now(dt.timezone.utc)
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_premium.is_(True), User.premium_until.is_not(None), User.premium_until < now)
        )
        expired = list(result.scalars())
        for user in expired:
            user.is_premium = False
        if expired:
            logger.info("Expired premium for %s user(s)", len(expired))


def register_jobs(scheduler) -> None:
    """Wire all recurring jobs onto an APScheduler AsyncIOScheduler instance."""
    scheduler.add_job(expire_premium_job, "interval", minutes=30, id="expire_premium", replace_existing=True)
