from __future__ import annotations

import asyncio
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.bot import build_application
from core.cache import ping as redis_ping
from core.config import get_settings
from core.logging import get_logger, setup_logging
from database.session import check_connection, init_models
from scheduler.jobs import register_jobs

logger = get_logger(__name__)


async def _preflight() -> None:
    """Fail fast with a clear, actionable message instead of a bare
    traceback when DATABASE_URL/REDIS_URL/BOT_TOKEN are wrong - this is
    exactly the class of bug that silently breaks `/start` on a fresh
    deploy (bad DB driver, unreachable Redis, expired token, etc.)."""
    settings = get_settings()

    logger.info("Checking database connectivity...")
    await check_connection()
    logger.info("Database OK.")

    logger.info("Checking Redis connectivity...")
    if not await redis_ping():
        logger.error(
            "Could not reach Redis at REDIS_URL='%s'. Cooldowns (daily/work/adventure/hunt/fight) "
            "will not work correctly. Check the host/port/password and that this network can reach it.",
            settings.redis_url,
        )
        # Redis failure is treated as non-fatal (cooldowns degrade rather
        # than the whole bot refusing to boot), but it's loud in the logs.
    else:
        logger.info("Redis OK.")

    if not settings.owner_ids:
        logger.warning(
            "OWNER_IDS is empty - nobody will have BOT_OWNER access (broadcast, maintenance, "
            "/editui, /shutdown, /lotterydraw all require it). Set OWNER_IDS in your environment."
        )


async def _async_main() -> None:
    setup_logging()
    logger.info("Starting Hela Bot...")

    try:
        await _preflight()
    except Exception as exc:
        logger.error("Preflight check failed - refusing to start. %s", exc)
        sys.exit(1)

    # Dev convenience: creates tables if they don't exist yet. In production,
    # run `alembic upgrade head` as part of your deploy step instead and skip
    # this (it's a no-op against a schema alembic already manages).
    await init_models()

    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)
    scheduler.start()

    application = build_application()

    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=["message", "callback_query", "chat_member"])
        logger.info("Hela Bot is up and polling.")
        try:
            await asyncio.Event().wait()  # run forever until cancelled
        finally:
            await application.updater.stop()
            await application.stop()
            scheduler.shutdown()


def main() -> None:
    try:
        asyncio.run(_async_main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Hela Bot shutting down.")


if __name__ == "__main__":
    main()
