from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session():
    """Usage: async with get_session() as session: ..."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models() -> None:
    """Create all tables. Convenience for local/dev; production deployments
    should use `alembic upgrade head` instead (see /alembic)."""
    from database.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_connection() -> None:
    """Raises with a clear, actionable message instead of the app dying
    silently on a bad DATABASE_URL (mismatched driver, wrong password,
    firewalled host, etc.) - call this once at startup."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - intentionally broad, re-raised with context
        raise RuntimeError(
            "Could not connect to the database using DATABASE_URL="
            f"'{settings.database_url}'. Check the host/port/credentials, "
            "that the driver is postgresql+asyncpg:// (not plain postgresql://), "
            f"and that this network can reach it. Original error: {exc!r}"
        ) from exc
