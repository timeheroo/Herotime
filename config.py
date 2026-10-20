import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Railway environment variables work without python-dotenv.
    pass


def get_required_env(name: str) -> str:
    """Read a required environment variable."""
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


def parse_admin_ids(value: str) -> set[int]:
    """Parse comma-separated Telegram user IDs."""
    ids = set()

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        try:
            telegram_id = int(item)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid Telegram admin ID: {item}"
            ) from exc

        if telegram_id <= 0:
            raise RuntimeError(
                "Admin IDs must be positive Telegram user IDs."
            )

        ids.add(telegram_id)

    return ids


# Telegram bot configuration
BOT_TOKEN = get_required_env("BOT_TOKEN")

# Example: ADMIN_IDS=123456789,987654321
ADMIN_IDS = parse_admin_ids(
    os.getenv("ADMIN_IDS", "")
)

if not ADMIN_IDS:
    raise RuntimeError(
        "Set at least one owner Telegram ID in ADMIN_IDS."
    )


# PostgreSQL connection string from Railway
DATABASE_URL = get_required_env("DATABASE_URL")


# Application settings
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

if LOG_LEVEL not in {
    "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
}:
    LOG_LEVEL = "INFO"


# Logging configuration
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("telegram_community_manager")


def is_admin(telegram_id: int) -> bool:
    """Return True only for configured admin Telegram IDs."""
    return telegram_id in ADMIN_IDS
