
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


def get_optional_env(name: str):
    value = os.getenv(name)
    return value.strip() if value else None


BOT_TOKEN = get_required_env("BOT_TOKEN")
OWNER_ADMIN_ID = int(get_required_env("OWNER_ADMIN_ID"))
DATABASE_URL = get_required_env("DATABASE_URL")

# Optional Telegram API credentials.
# Keep these values in Railway Variables, not in source code.
_api_id_value = get_optional_env("TELEGRAM_API_ID")
_api_hash_value = get_optional_env("TELEGRAM_API_HASH")

if bool(_api_id_value) != bool(_api_hash_value):
    raise RuntimeError(
        "TELEGRAM_API_ID and TELEGRAM_API_HASH "
        "must either both be set or both be empty."
    )

if _api_id_value:
    try:
        TELEGRAM_API_ID = int(_api_id_value)
    except ValueError as exc:
        raise RuntimeError(
            "TELEGRAM_API_ID must be a number."
        ) from exc

    if TELEGRAM_API_ID <= 0:
        raise RuntimeError(
            "TELEGRAM_API_ID must be greater than zero."
        )
else:
    TELEGRAM_API_ID = None

TELEGRAM_API_HASH = _api_hash_value

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
