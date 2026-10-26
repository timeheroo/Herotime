
"""
Live admin quantity and service controls.
Target must already exist in the database.
"""

import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import database
from live_campaigns import (
    get_live_settings,
    set_live_quantity,
    set_service_active,
)

logger = logging.getLogger(__name__)
MAX_QUANTITY = 100000


async def admin_only(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or not config.is_admin(user.id):
        if message:
            await message.reply_text(
                "⛔ Sirf authorized admin is command ko use kar sakta hai."
            )
        return False

    return True


def normalize_reference(value: str) -> str:
    value = value.strip().rstrip(".,;")

    if not value:
        return ""

    if value.startswith(("https://", "http://")):
        parsed = urlparse(value)
        host = parsed.netloc.lower()

        if host not in ("t.me", "www.t.me", "telegram.me",
                        "www.telegram.me"):
            return value

        path = parsed.path.strip("/")

        # Private invite links are kept unchanged.
        if path.startswith("+") or path.startswith("joinchat/"):
            return value.rstrip("/")

        if path:
            return "@" + path.split("/")[0]

        return ""

    if value.startswith(("t.me/", "telegram.me/")):
        return normalize_reference("https://" + value)

    if value.startswith("@"):
        return value

    return "@" + value


async def resolve_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        value: str):
    """
    Find a previously registered group by Telegram username/link.
    Database group IDs remain the internal identifiers.
    """
    reference = normalize_reference(value)
    if not reference:
        return None, None

    async with database.connection() as conn:
        # First try the saved invite URL or saved title.
        row = await conn.fetchrow(
            """
            SELECT id, title
            FROM groups
            WHERE LOWER(COALESCE(invite_url, '')) = LOWER($1)
               OR LOWER(title) = LOWER($2)
            ORDER BY id DESC
            LIMIT 1
            """,
            value.strip().rstrip("/"),
            reference,
        )

        if row:
            return int(row["id"]), str(row["title"])

        # Numeric Telegram chat ID or internal group ID.
        if reference.lstrip("-").isdigit():
            number = int(reference)
            row = await conn.fetchrow(
                """
                SELECT id, title
                FROM groups
                WHERE telegram_chat_id = $1 OR id = $1
                ORDER BY (telegram_chat_id = $1) DESC
                LIMIT 1
                """,
                number,
            )
            if row:
                return int(row["id"]), str(row["title"])

        # Some projects save the public username in the title field.
        username = reference[1:] if reference.startswith("@") else reference
        row = await conn.fetchrow(
            """
            SELECT id, title
            FROM groups
            WHERE LOWER(title) IN (LOWER($1), LOWER($2))
            ORDER BY id DESC
            LIMIT 1
            """,
            reference,
            username,
        )

        if row:
            return int(row["id"]), str(row["title"])

    # Ask Telegram to resolve a public username, then match its chat ID.
    if reference.startswith("@"):
        try:
            chat = await context.bot.get_chat(reference)

            async with database.connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, title
                    FROM groups
                    WHERE telegram_chat_id = $1
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    int(chat.id),
                )

            if row:
                return int(row["id"]), str(row["title"])

        except Exception:
            logger.info("Username lookup failed: %s", reference,
                        exc_info=True)

    return None, None


async def set_quantity_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage:\n"
            "/set_quantity @channelusername 100\n"
            "/set_quantity https://t.me/channelusername 100"
        )
        return

    try:
        group_id, title = await resolve_group(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered group/channel nahi mila. "
                "Pehle group add karein aur username/link check karein."
            )
            return

        quantity = int(context.args[1])
        if not 1 <= quantity <= MAX_QUANTITY:
            raise ValueError

        await set_live_quantity(group_id, quantity)

        await message.reply_text(
            f"✅ {title}\nQuantity set: {quantity}"
        )

    except ValueError:
        await message.reply_text(
            f"❌ Quantity 1 se {MAX_QUANTITY} ke beech honi chahiye."
        )
    except Exception:
        logger.exception("set_quantity failed")
        await message.reply_text(
            "❌ Quantity update nahi hui. Database schema aur Railway logs check karein."
        )


async def change_quantity(update: Update,
                          context: ContextTypes.DEFAULT_TYPE,
                          increase: bool):
    if not await admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    command = "increase_quantity" if increase else "decrease_quantity"

    if len(context.args) != 2:
        await message.reply_text(
            f"Usage:\n/{command} @channelusername 10\n"
            f"/{command} https://t.me/channelusername 10"
        )
        return

    try:
        group_id, title = await resolve_group(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered group/channel nahi mila. Username/link check karein."
            )
            return

        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError

        settings = await get_live_settings(group_id)
        if not settings:
            await message.reply_text(
                "❌ Live settings nahi mili. Pehle /set_quantity chalayein."
            )
            return

        old_quantity = int(settings["target_viewers"])
        new_quantity = (
            old_quantity + amount if increase
            else old_quantity - amount
        )

        if not 1 <= new_quantity <= MAX_QUANTITY:
            await message.reply_text(
                f"❌ Updated quantity 1 se {MAX_QUANTITY} ke beech honi chahiye."
            )
            return

        await set_live_quantity(group_id, new_quantity)

        action = "badha di" if increase else "ghata di"
        await message.reply_text(
            f"✅ {title}\n"
            f"Purani quantity: {old_quantity}\n"
            f"Nayi quantity: {new_quantity}\n"
            f"Quantity {action} gayi."
        )

    except ValueError:
        await message.reply_text(
            "❌ Amount positive whole number hona chahiye."
        )
    except Exception:
        logger.exception("%s failed", command)
        await message.reply_text(
            "❌ Quantity change nahi hui. Railway logs check karein."
        )


async def increase_quantity_command(update, context):
    await change_quantity(update, context, True)


async def decrease_quantity_command(update, context):
    await change_quantity(update, context, False)
  
async def change_service(update: Update,
                         context: ContextTypes.DEFAULT_TYPE,
                         enabled: bool):
    if not await admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    command = "start_service" if enabled else "stop_service"

    if len(context.args) != 1:
        await message.reply_text(
            f"Usage:\n/{command} @channelusername\n"
            f"/{command} https://t.me/channelusername"
        )
        return

    try:
        group_id, title = await resolve_group(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered group/channel nahi mila. Username/link check karein."
            )
            return

        await set_service_active(group_id, enabled)

        status = "STARTED 🟢" if enabled else "STOPPED 🔴"
        await message.reply_text(
            f"✅ {title}\nService status: {status}\n"
            "Note: actual service worker ko bhi is status ko follow karna hoga."
        )

    except Exception:
        logger.exception("%s failed", command)
        await message.reply_text(
            "❌ Service status update nahi hua. Railway logs check karein."
        )


async def start_service_command(update, context):
    await change_service(update, context, True)


async def stop_service_command(update, context):
    await change_service(update, context, False)


async def live_status_command(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage:\n/live_status @channelusername\n"
            "/live_status https://t.me/channelusername"
        )
        return

    try:
        group_id, title = await resolve_group(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered group/channel nahi mila. Username/link check karein."
            )
            return

        settings = await get_live_settings(group_id)
        if not settings:
            await message.reply_text(
                f"❌ {title}: live settings nahi mili."
            )
            return

        await message.reply_text(
            "📊 Service Status\n\n"
            f"Group/channel: {settings['title']}\n"
            f"Target quantity: {settings['target_viewers']}\n"
            f"Group active: {settings['group_is_active']}\n"
            f"Service active: {settings['service_active']}\n"
            f"Stream status: {settings['stream_status']}\n"
            f"Last event: {settings['last_event_at'] or 'None'}"
        )

    except Exception:
        logger.exception("live_status failed")
        await message.reply_text(
            "❌ Status load nahi hua. Database aur Railway logs check karein."
        )


async def all_services_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    try:
        async with database.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT g.id, g.title, g.group_type, g.service_active,
                       s.target_viewers, s.stream_status
                FROM groups AS g
                LEFT JOIN live_campaign_settings AS s
                    ON s.group_id = g.id
                ORDER BY g.id DESC
                LIMIT 100
                """
            )

        if not rows:
            await message.reply_text("Koi group/channel registered nahi hai.")
            return

        lines = ["📋 All Group/Channel Services"]

        for row in rows:
            quantity = row["target_viewers"]
            lines.append(
                f"\n{row['title']}\n"
                f"Type: {row['group_type']}\n"
                f"Service active: {row['service_active']}\n"
                f"Target quantity: {quantity if quantity is not None else 'Not set'}\n"
                f"Stream status: {row['stream_status'] or 'unknown'}"
            )

        output = "\n".join(lines)
        for start in range(0, len(output), 3500):
            await message.reply_text(output[start:start + 3500])

    except Exception:
        logger.exception("all_services failed")
        await message.reply_text(
            "❌ Services list nahi hui. Database schema aur Railway logs check karein."
        )


def register_live_admin_handlers(application: Application) -> None:
    handlers = [
        ("set_quantity", set_quantity_command),
        ("increase_quantity", increase_quantity_command),
        ("decrease_quantity", decrease_quantity_command),
        ("start_service", start_service_command),
        ("stop_service", stop_service_command),
        ("live_status", live_status_command),
        ("all_services", all_services_command),
    ]

    for command, callback in handlers:
        application.add_handler(CommandHandler(command, callback))

async def set_quantity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage: /set_quantity @username QUANTITY\n"
            "Example: /set_quantity @yourchannel 100"
        )
        return

    # Quantity ko alag validate karein.
    try:
        quantity = int(context.args[1])
        if not 1 <= quantity <= MAX_QUANTITY:
            raise ValueError
    except (ValueError, TypeError):
        await message.reply_text(
            f"❌ Quantity 1 se {MAX_QUANTITY} ke beech whole number honi chahiye."
        )
        return

    try:
        group_id, title = await _resolve_from_update(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered channel nahi mila. Pehle /add_group se register karein."
            )
            return

        await set_live_quantity(group_id, quantity)
        await message.reply_text(
            f"✅ {title}\nTarget quantity {quantity} set ho gayi."
        )

    except Exception:
        logger.exception("set_quantity failed")
        await message.reply_text(
            "❌ Quantity save nahi hui. Railway logs mein asli error check karein. "
            "Channel ka group_type 'target' hona chahiye."
        )


async def _change_quantity(update, context, increase: bool):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    command = "increase_quantity" if increase else "decrease_quantity"

    if len(context.args) != 2:
        await message.reply_text(
            f"Usage: /{command} @username AMOUNT\n"
            f"Example: /{command} @yourchannel 10"
        )
        return

    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.reply_text(
            "❌ Amount positive whole number hona chahiye. Example: 10"
        )
        return

    try:
        group_id, title = await _resolve_from_update(
            update, context, context.args[0]
        )

        if group_id is None:
            await message.reply_text(
                "❌ Registered channel nahi mila. Username aur /add_group check karein."
            )
            return

        current = await get_live_settings(group_id)
        if not current:
            await message.reply_text(
                "❌ Live settings nahi mili. Pehle /set_quantity chalayein."
            )
            return

        old = int(current["target_viewers"])
        new = old + amount if increase else old - amount

        if not 1 <= new <= MAX_QUANTITY:
            await message.reply_text(
                f"❌ Nayi quantity 1 se {MAX_QUANTITY} ke beech honi chahiye."
            )
            return

        await set_live_quantity(group_id, new)

        await message.reply_text(
            f"✅ {title}\n"
            f"Purani quantity: {old}\n"
            f"Nayi quantity: {new}\n"
            f"Quantity {'badha di' if increase else 'ghata di'}."
        )

    except Exception:
        logger.exception("%s failed", command)
        await message.reply_text(
            "❌ Quantity change nahi hui. Railway logs check karein; "
            "channel ka group_type 'target' hona chahiye."
        )


async def increase_quantity_command(update, context):
    await _change_quantity(update, context, True)


async def decrease_quantity_command(update, context):
    await _change_quantity(update, context, False)
