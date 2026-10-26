
import re
from urllib.parse import urlparse


def validate_telegram_user_id(value: str) -> int:
    """Validate a numeric Telegram user ID."""
    value = value.strip()

    if not value.isdigit():
        raise ValueError("Telegram user ID numeric hona chahiye.")

    user_id = int(value)

    if user_id <= 0:
        raise ValueError("Telegram user ID positive hona chahiye.")

    return user_id


def validate_quantity(value: str) -> int:
    """Validate a non-negative quantity."""
    value = value.strip()

    if not value.isdigit():
        raise ValueError("Quantity mein sirf numbers enter karein.")

    quantity = int(value)

    if quantity > 1_000_000:
        raise ValueError("Quantity allowed limit se zyada hai.")

    return quantity


def validate_channel_username(value: str) -> str:
    """Normalize and validate a public channel username."""
    value = value.strip()

    value = re.sub(
        r"^https?://(www\.)?t\.me/",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.split("?")[0].strip("/")

    if value.startswith("@"):
        value = value[1:]

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
        raise ValueError(
            "Valid public channel username ya t.me link enter karein."
        )

    return "@" + value


def validate_telegram_link(value: str) -> str:
    """Validate a Telegram URL."""
    value = value.strip()

    parsed = urlparse(value)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Link http:// ya https:// se shuru hona chahiye.")

    if parsed.netloc.lower() not in ("t.me", "www.t.me", "telegram.me"):
        raise ValueError("Valid Telegram link enter karein.")

    if not parsed.path.strip("/"):
        raise ValueError("Telegram link mein channel ya group path missing hai.")

    return value
