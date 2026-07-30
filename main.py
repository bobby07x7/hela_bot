from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.bot import build_application
from core.logging import get_logger, setup_logging
from database.session import init_models
from scheduler.jobs import register_jobs

logger = get_logger(__name__)


async def _async_main() -> None:
    setup_logging()
    logger.info("Starting Hela Bot...")

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
