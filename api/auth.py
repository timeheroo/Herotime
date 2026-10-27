
"""Telegram Mini App initData authentication."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, status

from config import BOT_TOKEN


MAX_INIT_DATA_AGE_SECONDS = 3600


def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram Web App initData and return validated user data."""
    if not init_data or len(init_data) > 16_384:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Telegram initData.",
        )

    try:
        parsed_items = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
        data = dict(parsed_items)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Telegram initData.",
        ) from exc

    received_hash = data.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram signature is missing.",
        )

    # Telegram Web Apps HMAC validation:
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

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram signature verification failed.",
        )

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication timestamp.",
        ) from exc

    now = int(time.time())

    if auth_date <= 0 or auth_date > now + 30:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication timestamp.",
        )

    if now - auth_date > MAX_INIT_DATA_AGE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram login has expired. Reopen the Mini App.",
        )

    user_json = data.get("user")

    if not user_json:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram user information is missing.",
        )

    try:
        user = json.loads(user_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram user information.",
        ) from exc

    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram user information.",
        )

    return {
        "user": user,
        "auth_date": auth_date,
    }


async def get_current_telegram_user(request: Request) -> dict:
    """Authenticate a request using its Telegram initData header."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    verified = verify_telegram_init_data(init_data)
    return verified["user"]
