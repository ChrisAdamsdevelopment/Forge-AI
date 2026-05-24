"""
forge/core/database.py

Async SQLAlchemy engine + session factory for SQLite (WAL mode).
All ORM models live in forge/core/models.py.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

from forge.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.db_url,
    echo=settings.log_level == "debug",
    connect_args={"check_same_thread": False},
)


# Enable WAL mode for better concurrent read performance
@event.listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that provides a transactional database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables defined in models.py. Called at app startup."""
    from forge.core import models as _  # noqa: F401 – ensures models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
