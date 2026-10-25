import logging
from telegram import Bot
from telegram.error import TelegramError

from config import ADMIN_IDS
from database import get_pool

logger = logging.getLogger(__name__)


async def init_notification_schema() -> None:
    """Create the announcement opt-in field if it does not exist."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS
            broadcast_opt_in BOOLEAN NOT NULL DEFAULT FALSE
            """
        )


async def set_announcement_opt_in(
    telegram_id: int,
    enabled: bool,
) -> bool:
    """Allow a user to opt in or out of announcements."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE users
            SET broadcast_opt_in = $2
            WHERE telegram_id = $1
              AND status = 'approved'
            """,
            telegram_id,
            enabled,
        )

    return result.endswith("1")


async def send_user_notification(
    bot: Bot,
    telegram_id: int,
    message: str,
) -> bool:
    """Send a notification to one user who has started the bot."""
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
        )
        return True

    except TelegramError as exc:
        logger.warning(
            "Could not notify Telegram user %s: %s",
            telegram_id,
            exc,
        )
        return False


async def notify_admins(
    bot: Bot,
    message: str,
) -> int:
    """Send an operational notification to configured bot admins."""
    sent = 0

    for admin_id in ADMIN_IDS:
        if await send_user_notification(bot, admin_id, message):
            sent += 1

    return sent


async def send_opted_in_announcement(
    bot: Bot,
    message: str,
) -> dict:
    """
    Send an announcement only to approved users
    who explicitly opted in.
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetch(
            """
            SELECT telegram_id
            FROM users
            WHERE status = 'approved'
              AND broadcast_opt_in = TRUE
            ORDER BY telegram_id
            """
        )

    sent = 0
    failed = 0

    for user in users:
        success = await send_user_notification(
            bot,
            user["telegram_id"],
            message,
        )

        if success:
            sent += 1
        else:
            failed += 1

    logger.info(
        "Opt-in announcement finished: sent=%s failed=%s",
        sent,
        failed,
    )

    return {
        "eligible": len(users),
        "sent": sent,
        "failed": failed,
    }
