
"""
live_admin.py — Admin commands for per-group campaign settings.
GROUP_ID means the internal database groups.id.
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from live_campaigns import (
    get_live_settings,
    set_live_quantity,
    set_service_active,
)

logger = logging.getLogger(__name__)


async def _admin_only(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or not config.is_admin(user.id):
        if message:
            await message.reply_text("⛔ Ye command sirf admin use kar sakta hai.")
        return False

    return True


async def _get_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    if not context.args:
        if message:
            await message.reply_text(
                "Database Group ID dena zaroori hai.\n"
                "Example: /live_status 1"
            )
        return None

    try:
        group_id = int(context.args[0])
        if group_id <= 0:
            raise ValueError
        return group_id
    except ValueError:
        if message:
            await message.reply_text(
                "❌ Group ID positive database ID hona chahiye, "
                "jaise /live_status 1"
            )
        return None


async def set_quantity_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage: /set_quantity GROUP_ID QUANTITY\n"
            "Example: /set_quantity 1 100"
        )
        return

    try:
        group_id = int(context.args[0])
        quantity = int(context.args[1])

        if group_id <= 0 or not 1 <= quantity <= 100000:
            raise ValueError

        await set_live_quantity(group_id, quantity)
        await message.reply_text(
            f"✅ Group ID {group_id} ki target quantity {quantity} set ho gayi."
        )

    except ValueError:
        await message.reply_text(
            "❌ Group ID positive number aur quantity 1 se 100000 ke beech honi chahiye."
        )
    except Exception:
        logger.exception("set_quantity failed")
        await message.reply_text(
            "❌ Quantity update nahi hui. Group ID aur Railway logs check karein."
        )


async def _change_quantity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    increase: bool,
):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        command = "increase_quantity" if increase else "decrease_quantity"
        await message.reply_text(
            f"Usage: /{command} GROUP_ID AMOUNT\n"
            f"Example: /{command} 1 10"
        )
        return

    try:
        group_id = int(context.args[0])
        amount = int(context.args[1])

        if group_id <= 0 or amount <= 0:
            raise ValueError

        current = await get_live_settings(group_id)
        if not current:
            await message.reply_text(
                "❌ Group ki live settings nahi mili. "
                "Pehle /set_quantity GROUP_ID QUANTITY chalayein."
            )
            return

        old_quantity = int(current["target_viewers"])
        new_quantity = old_quantity + amount if increase else old_quantity - amount

        if not 1 <= new_quantity <= 100000:
            await message.reply_text(
                "❌ Nayi quantity 1 se 100000 ke beech honi chahiye."
            )
            return

        await set_live_quantity(group_id, new_quantity)
        operation = "badha di" if increase else "ghata di"

        await message.reply_text(
            f"✅ Group ID {group_id}\n"
            f"Purani target quantity: {old_quantity}\n"
            f"Nayi target quantity: {new_quantity}\n"
            f"Quantity {operation} gayi."
        )

    except ValueError:
        await message.reply_text(
            "❌ Group ID aur amount positive numbers hone chahiye."
        )
    except Exception:
        logger.exception("Quantity adjustment failed")
        await message.reply_text(
            "❌ Quantity change nahi hui. Railway logs check karein."
        )


async def increase_quantity_command(update, context):
    await _change_quantity(update, context, increase=True)


async def decrease_quantity_command(update, context):
    await _change_quantity(update, context, increase=False)


async def _service_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    enabled: bool,
):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    group_id = await _get_group_id(update, context)
    if group_id is None:
        return

    try:
        await set_service_active(group_id, enabled)
        state = "STARTED 🟢" if enabled else "STOPPED 🔴"

        await message.reply_text(
            f"✅ Group ID {group_id} ki service {state}.\n"
            "Note: Yeh database setting hai; actual worker ko is setting "
            "ko check karna hoga."
        )

    except Exception:
        logger.exception("Service status update failed")
        await message.reply_text(
            "❌ Service update nahi hui. Group ID aur database logs check karein."
        )


async def start_service_command(update, context):
    await _service_command(update, context, True)


async def stop_service_command(update, context):
    await _service_command(update, context, False)


async def live_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    group_id = await _get_group_id(update, context)
    if group_id is None:
        return

    try:
        settings = await get_live_settings(group_id)

        if not settings:
            await message.reply_text(
                f"Group ID {group_id} nahi mila ya live settings available nahi hain."
            )
            return

        await message.reply_text(
            f"📊 Live Service Status\n\n"
            f"Group ID: {settings['group_id']}\n"
            f"Name: {settings['title']}\n"
            f"Group active: {settings['group_is_active']}\n"
            f"Target quantity: {settings['target_viewers']}\n"
            f"Service active: {settings['service_active']}\n"
            f"Stream status: {settings['stream_status']}\n"
            f"Last event: {settings['last_event_at'] or 'None'}"
        )

    except Exception:
        logger.exception("live_status failed")
        await message.reply_text(
            "❌ Status load nahi hua. Railway logs check karein."
        )


async def all_services_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    try:
        from database import connection

        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT g.id, g.title, g.group_type, g.service_active,
                       s.target_viewers, s.stream_status
                FROM groups g
                LEFT JOIN live_campaign_settings s ON s.group_id = g.id
                ORDER BY g.id DESC
                LIMIT 100
                """
            )

        if not rows:
            await message.reply_text("Koi group/channel saved nahi hai.")
            return

        lines = ["📋 All Group/Channel Services"]
        for row in rows:
            lines.append(
                f"\nID: {row['id']} | {row['group_type']}\n"
                f"Name: {row['title']}\n"
                f"Service: {'Active' if row['service_active'] else 'Paused'}\n"
                f"Target: {row['target_viewers'] if row['target_viewers'] is not None else 'Not set'}\n"
                f"Stream status: {row['stream_status'] or 'unknown'}"
            )

        output = "\n".join(lines)
        for start in range(0, len(output), 3500):
            await message.reply_text(output[start:start + 3500])

    except Exception:
        logger.exception("all_services failed")
        await message.reply_text(
            "❌ Services list nahi hui. Railway logs check karein."
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
