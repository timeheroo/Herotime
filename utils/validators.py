
import re
from urllib.parse import urlparse


def validate_positive_int(value, field_name="Value"):
    """Convert a value to a positive integer."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a whole number.") from exc

    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return number


def validate_non_negative_int(value, field_name="Value"):
    """Convert a value to zero or a positive integer."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a whole number.") from exc

    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return number


def normalize_public_channel(value):
    """Normalize a public Telegram username or public channel URL."""
    if not isinstance(value, str):
        raise ValueError("Enter a Telegram username or public channel link.")

    value = value.strip()

    if not value:
        raise ValueError("Channel username cannot be empty.")

    if value.startswith("@"):
        username = value[1:]
    elif "://" in value:
        parsed = urlparse(value)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP or HTTPS Telegram links are accepted.")

        host = (parsed.hostname or "").lower()

        if host not in ("t.me", "www.t.me", "telegram.me", "www.telegram.me"):
            raise ValueError("Enter a public t.me or telegram.me link.")

        username = parsed.path.strip("/").split("/")[0]
    else:
        username = value

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", username):
        raise ValueError("Enter a valid public Telegram username.")

    return username


def validate_reaction_type(value):
    """Allow only supported reaction labels."""
    allowed = {
        "like",
        "heart",
        "fire",
        "thumbsup",
        "laugh",
        "sad",
        "wow",
    }

    if not isinstance(value, str):
        raise ValueError("Reaction type must be text.")

    reaction = value.strip().lower()

    if reaction not in allowed:
        raise ValueError(
            "Unsupported reaction type. Choose: "
            + ", ".join(sorted(allowed))
        )

    return reaction
