
import os
from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise RuntimeError(
            f"Required environment variable missing: {name}"
        )

    return value.strip()


# Telegram bot token
BOT_TOKEN = get_required_env("BOT_TOKEN")

# PostgreSQL database connection URL
DATABASE_URL = get_required_env("DATABASE_URL")

# Owner's numeric Telegram user ID
try:
    OWNER_ADMIN_ID = int(get_required_env("OWNER_ADMIN_ID"))
except ValueError as exc:
    raise RuntimeError(
        "OWNER_ADMIN_ID must be a valid numeric Telegram user ID."
    ) from exc

if OWNER_ADMIN_ID <= 0:
    raise RuntimeError(
        "OWNER_ADMIN_ID must be greater than zero."
    )

# Encryption disabled: no encryption key required.
CREDENTIAL_ENCRYPTION_KEY = ""

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
