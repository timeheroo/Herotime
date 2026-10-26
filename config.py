
import os
from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable missing: {name}"
        )

    return value


# Telegram bot configuration
BOT_TOKEN = get_required_env("BOT_TOKEN")

# Main owner/admin Telegram numeric user ID
OWNER_ADMIN_ID = int(get_required_env("OWNER_ADMIN_ID"))

# PostgreSQL database connection URL
DATABASE_URL = get_required_env("DATABASE_URL")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
