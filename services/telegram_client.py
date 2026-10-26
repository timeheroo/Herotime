
from telegram import Bot
from telegram.error import TelegramError

from config import BOT_TOKEN


async def get_telegram_bot() -> Bot:
    """Create a Telegram bot client."""
    return Bot(token=BOT_TOKEN)


async def check_channel_access(channel_id: str) -> dict:
    """
    Check whether the bot can access a channel.

    The bot must already be added to the channel.
    For private channels, use the numeric chat ID if known.
    """
    bot = await get_telegram_bot()

    try:
        chat = await bot.get_chat(channel_id)

        return {
            "success": True,
            "channel_id": chat.id,
            "title": chat.title or chat.full_name or "Unknown",
            "username": chat.username,
            "message": "Channel details retrieved successfully."
        }

    except TelegramError:
        return {
            "success": False,
            "channel_id": None,
            "title": None,
            "username": None,
            "message": (
                "Channel access failed. Check the channel ID or username, "
                "and make sure the bot has been added to the channel."
            )
        }
