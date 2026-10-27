
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from services.account_manager import (
    add_api_config,
    list_api_configs,
    rename_api_config,
    set_api_config_status,
    remove_api_config,
)
from utils.permissions import require_permission
from utils.logger import log_action

logger = logging.getLogger(__name__)


async def _authorized(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return False

    allowed, reason = await require_permission(
        user.id,
        "manage_accounts",
    )

    if not allowed:
        await message.reply_text(reason)
        return False

    return True


async def addapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message
    user = update.effective_user

    if len(context.args) < 3:
        await message.reply_text(
            "Usage:\n"
            "/addapi NAME API_ID API_HASH\n\n"
            "Example format:\n"
            "/addapi MainAccount 123456 your_api_hash"
        )
        return

    name = context.args[0]
    api_id_text = context.args[1]
    api_hash = context.args[2]

    try:
        api_id = int(api_id_text)

        config_id = await add_api_config(
            name=name,
            api_id=api_id,
            api_hash=api_hash,
            created_by=user.id,
        )

        await log_action(
            user.id,
            "api_config_added",
            {"config_id": config_id, "name": name},
        )

        await message.reply_text(
            f"API configuration added successfully.\n"
            f"ID: {config_id}\n"
            f"Name: {name}\n"
            f"API ID: {api_id}\n"
            f"Status: Active"
        )

    except ValueError as exc:
        await message.reply_text(f"Error: {exc}")
    except Exception:
        logger.exception("Failed to add API configuration")
        await message.reply_text(
            "API configuration add nahi ho saka. "
            "Server logs check karein; secrets share na karein."
        )


async def apiconfigs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    try:
        configs = await list_api_configs()

        if not configs:
            await message.reply_text(
                "Abhi koi API configuration saved nahi hai."
            )
            return

        lines = ["Saved API configurations:"]

        for item in configs:
            status = "ACTIVE" if item["is_active"] else "INACTIVE"
            lines.append(
                f"\nID: {item['id']}"
                f"\nName: {item['name']}"
                f"\nAPI ID: {item['api_id']}"
                f"\nStatus: {status}"
            )

        await message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Failed to list API configurations")
        await message.reply_text(
            "Configurations load nahi ho sakin."
        )


async def renameapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    if len(context.args) < 2:
        await message.reply_text(
            "Usage: /renameapi CONFIG_ID NEW_NAME\n"
            "Example: /renameapi 1 BackupAccount"
        )
        return

    try:
        config_id = int(context.args[0])
        new_name = " ".join(context.args[1:])

        changed = await rename_api_config(config_id, new_name)

        if not changed:
            await message.reply_text("Configuration ID nahi mila.")
            return

        await log_action(
            update.effective_user.id,
            "api_config_renamed",
            {"config_id": config_id, "new_name": new_name},
        )

        await message.reply_text(
            f"Configuration {config_id} ka naam update ho gaya."
        )

    except ValueError as exc:
        await message.reply_text(f"Error: {exc}")
    except Exception:
        logger.exception("Failed to rename API configuration")
        await message.reply_text("Configuration rename nahi ho saka.")


async def activateapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _change_status(update, context, True)


async def deactivateapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _change_status(update, context, False)


async def _change_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    active: bool,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /activateapi CONFIG_ID\n"
            "or /deactivateapi CONFIG_ID"
        )
        return

    try:
        config_id = int(context.args[0])
        changed = await set_api_config_status(config_id, active)

        if not changed:
            await message.reply_text("Configuration ID nahi mila.")
            return

        action = "api_config_activated" if active else "api_config_deactivated"

        await log_action(
            update.effective_user.id,
            action,
            {"config_id": config_id},
        )

        status = "ACTIVE" if active else "INACTIVE"
        await message.reply_text(
            f"Configuration {config_id} status: {status}"
        )

    except ValueError:
        await message.reply_text("Configuration ID numeric hona chahiye.")
    except Exception:
        logger.exception("Failed to change API configuration status")
        await message.reply_text("Status update nahi ho saka.")


async def removeapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /removeapi CONFIG_ID\n"
            "Warning: removal permanent hai."
        )
        return

    try:
        config_id = int(context.args[0])
        removed = await remove_api_config(config_id)

        if not removed:
            await message.reply_text("Configuration ID nahi mila.")
            return

        await log_action(
            update.effective_user.id,
            "api_config_removed",
            {"config_id": config_id},
        )

        await message.reply_text(
            f"Configuration {config_id} remove ho gaya."
        )

    except ValueError:
        await message.reply_text("Configuration ID numeric hona chahiye.")
    except Exception:
        logger.exception("Failed to remove API configuration")
        await message.reply_text("Configuration remove nahi ho saka.")


def get_account_handlers():
    return [
        CommandHandler("addapi", addapi),
        CommandHandler("apiconfigs", apiconfigs),
        CommandHandler("renameapi", renameapi),
        CommandHandler("activateapi", activateapi),
        CommandHandler("deactivateapi", deactivateapi),
        CommandHandler("removeapi", removeapi),
    ]
