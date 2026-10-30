
"""Secure Telegram Mini App initData authentication."""

import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, status

from config import BOT_TOKEN


MAX_INIT_DATA_AGE_SECONDS = 3600
MAX_INIT_DATA_LENGTH = 16_384
MAX_INIT_DATA_FIELDS = 100

HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def unauthorized(detail: str) -> HTTPException:
    """Create a standard authentication error."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram Web App initData and return validated user data."""

    if (
        not isinstance(init_data, str)
        or not init_data
        or len(init_data) > MAX_INIT_DATA_LENGTH
    ):
        raise unauthorized("Missing or invalid Telegram initData.")

    try:
        parsed_items = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=MAX_INIT_DATA_FIELDS,
            encoding="utf-8",
            errors="strict",
        )
    except (ValueError, UnicodeError) as exc:
        raise unauthorized("Malformed Telegram initData.") from exc

    # Reject duplicate keys to prevent parameter ambiguity.
    keys = [key for key, _ in parsed_items]

    if len(keys) != len(set(keys)):
        raise unauthorized("Duplicate Telegram initData parameters.")

    data = dict(parsed_items)

    received_hash = data.pop("hash", None)

    if not received_hash or not HASH_PATTERN.fullmatch(received_hash):
        raise unauthorized("Invalid or missing Telegram signature.")

    # Telegram Web Apps HMAC validation.
    # secret_key = HMAC_SHA256(key="WebAppData", message=bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
    )

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash.lower()):
        raise unauthorized("Telegram signature verification failed.")

    # Validate authentication timestamp.
    try:
        auth_date_value = data.get("auth_date", "")
        auth_date = int(auth_date_value)

        if str(auth_date) != auth_date_value:
            raise ValueError("Invalid timestamp format.")

    except (ValueError, TypeError) as exc:
        raise unauthorized("Invalid authentication timestamp.") from exc

    now = int(time.time())

    if auth_date <= 0 or auth_date > now + 30:
        raise unauthorized("Invalid authentication timestamp.")

    if now - auth_date > MAX_INIT_DATA_AGE_SECONDS:
        raise unauthorized(
            "Telegram login has expired. Reopen the Mini App."
        )

    # Validate Telegram user information.
    user_json = data.get("user")

    if not user_json:
        raise unauthorized("Telegram user information is missing.")

    try:
        user = json.loads(user_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise unauthorized("Invalid Telegram user information.") from exc

    if not isinstance(user, dict):
        raise unauthorized("Invalid Telegram user information.")

    telegram_id = user.get("id")

    if (
        not isinstance(telegram_id, int)
        or isinstance(telegram_id, bool)
        or telegram_id <= 0
    ):
        raise unauthorized("Invalid Telegram user ID.")

    return {
        "user": user,
        "auth_date": auth_date,
    }


async def get_current_telegram_user(request: Request) -> dict:
    """Authenticate a request using its Telegram initData header."""

    init_data = request.headers.get("X-Telegram-Init-Data", "")

    verified = verify_telegram_init_data(init_data)

    return verified["user"]
