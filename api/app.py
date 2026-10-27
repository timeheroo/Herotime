
"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from api.routes import admin, accounts, channels, monitoring, reactions, reports
from database.connection import close_database, init_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and close shared database resources."""
    logger.info("Initializing database connection...")
    await init_database()

    try:
        yield
    finally:
        await close_database()
        logger.info("Database connection closed.")


app = FastAPI(
    title="Telegram Management API",
    description="API for Telegram channel and account management.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(channels.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(reactions.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
async def root():
    """Basic service information."""
    return {
        "service": "Telegram Management API",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Check whether PostgreSQL is reachable."""
    from database.connection import get_session_factory

    session_factory = get_session_factory()

    async with session_factory() as session:
        await session.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
    }
