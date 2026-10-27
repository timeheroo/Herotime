
"""FastAPI application for the Telegram management system."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.connection import close_database, init_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle."""
    await init_database()
    logger.info("API database connection verified.")

    try:
        yield
    finally:
        await close_database()
        logger.info("API shutdown complete.")


app = FastAPI(
    title="Telegram Management API",
    description="Backend API for the Telegram bot and Mini App.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Basic API information."""
    return {
        "name": "Telegram Management API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Check API and database availability."""
    from sqlalchemy import text

    from database.connection import engine

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
    }
