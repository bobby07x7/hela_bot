from __future__ import annotations

from contextlib import asynccontextmanager

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
