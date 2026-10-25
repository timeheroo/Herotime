
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import is_admin
from live_campaigns import (
    get_live_settings,
    set_live_quantity,
    set_service_active,
)


async def quantity_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "You are not authorized to use this command."
        )
        return

    if len(context.args) != 2:
        await update.effective_message.reply_text(
            "Usage: /set_quantity GROUP_ID QUANTITY\n"
            "Example: /set_quantity 12 100"
        )
        return

    try:
        group_id = int(context.args[0])
        quantity = int(context.args[1])

        if group_id <= 0:
            raise ValueError

        if not 1 <= quantity <= 100000:
            await update.effective_message.reply_text(
                "Quantity must be between 1 and 100000."
            )
            return

    except ValueError:
        await update.effective_message.reply_text(
            "Please enter a valid positive group ID and quantity."
        )
        return

    try:
        saved = await set_live_quantity(group_id, quantity)
    except Exception:
        await update.effective_message.reply_text(
            "Could not save the quantity. Check the database logs."
        )
        raise

    if not saved:
        await update.effective_message.reply_text(
            "Target group not found. Add it to the database first."
        )
        return

    await update.effective_message.reply_text(
        f"Campaign target saved: {quantity}\n"
        f"Group ID: {group_id}\n"
        "This is a campaign target, not a guaranteed viewer count."
    )


async def start_service_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _toggle_service(update, context, enabled=True)


async def stop_service_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _toggle_service(update, context, enabled=False)


async def _toggle_service(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    enabled: bool,
) -> None:
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "You are not authorized to use this command."
        )
        return

    if len(context.args) != 1:
        command = "start_service" if enabled else "stop_service"
        await update.effective_message.reply_text(
            f"Usage: /{command} GROUP_ID"
        )
        return

    try:
        group_id = int(context.args[0])
        if group_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "Please enter a valid positive group ID."
        )
        return

    try:
        saved = await set_service_active(group_id, enabled)
    except Exception:
        await update.effective_message.reply_text(
            "Could not update service status. Check database logs."
        )
        raise

    if not saved:
        await update.effective_message.reply_text(
            "Target group not found. Add it to the database first."
        )
        return

    status = "ON" if enabled else "OFF"
    await update.effective_message.reply_text(
        f"Campaign service is now {status} for group {group_id}."
    )


async def live_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "You are not authorized to use this command."
        )
        return

    if len(context.args) != 1:
        await update.effective_message.reply_text(
            "Usage: /live_status GROUP_ID"
        )
        return

    try:
        group_id = int(context.args[0])
        if group_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "Please enter a valid positive group ID."
        )
        return

    try:
        settings = await get_live_settings(group_id)
    except Exception:
        await update.effective_message.reply_text(
            "Could not read status. Check database logs."
        )
        raise

    if settings is None:
        await update.effective_message.reply_text(
            "Target group not found."
        )
        return

    await update.effective_message.reply_text(
        f"Group: {settings['title']}\n"
        f"Group active: {settings['group_is_active']}\n"
        f"Campaign target: {settings['target_viewers']}\n"
        f"Service active: {settings['service_active']}\n"
        f"Saved stream status: {settings['stream_status']}\n\n"
        "Stream status is only as current as the last event received."
    )


def register_live_admin_handlers(application) -> None:
    application.add_handler(
        CommandHandler("set_quantity", quantity_command)
    )
    application.add_handler(
        CommandHandler("start_service", start_service_command)
    )
    application.add_handler(
        CommandHandler("stop_service", stop_service_command)
    )
    application.add_handler(
        CommandHandler("live_status", live_status_command)
    )
