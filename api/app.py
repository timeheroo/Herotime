
"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from api.routers import (
    account,
    admin,
    channels,
    monitoring,
    reactions,
    reports,
)
from database.connection import (
    close_database,
    create_tables,
    engine,
    init_database,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and close shared database resources."""
    try:
        logger.info("Checking PostgreSQL connection...")
        await init_database()

        logger.info("Ensuring database tables exist...")
        await create_tables()

        logger.info("FastAPI application started.")
        yield

    finally:
        await close_database()
        logger.info("FastAPI database resources closed.")


app = FastAPI(
    title="Telegram Management API",
    description="API for Telegram channel and account management.",
    version="1.0.0",
    lifespan=lifespan,
)


# Register API routers
app.include_router(channels.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(reactions.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": "Telegram Management API",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Check API and PostgreSQL connectivity."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    except Exception:
        logger.exception("Health check failed.")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    return {
        "status": "healthy",
        "database": "connected",
    }
