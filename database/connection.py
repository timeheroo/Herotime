
"""Async PostgreSQL connection and session management."""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL


engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide a database session and close it automatically."""
    async with SessionFactory() as session:
        yield session


async def init_database() -> None:
    """Check the database connection."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def create_tables() -> None:
    """Create tables defined in the SQLAlchemy models."""
    from database.models import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """Dispose of the database connection pool."""
    await engine.dispose()
