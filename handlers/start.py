
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes

from config import OWNER_ADMIN_ID
from utils.permissions import get_admin, has_permission


MENU = ReplyKeyboardMarkup(
    [
        ["API Accounts", "Channels / Groups"],
        ["Live Tasks", "Reaction Tasks"],
        ["Reports", "Admin Help"],
    ],
    resize_keyboard=True,
)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    admin = await get_admin(user.id)

    if admin is None and user.id != OWNER_ADMIN_ID:
        await message.reply_text(
            "Access denied. Bot owner se access request karein."
        )
        return

    await message.reply_text(
        "Welcome to the Admin Management Bot.\n\n"
        "Menu se section select karein. "
        "Available actions aapki permissions par depend karte hain.",
        reply_markup=MENU,
    )


async def menu_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None or not message.text:
        return

    admin = await get_admin(user.id)

    if admin is None and user.id != OWNER_ADMIN_ID:
        await message.reply_text("Access denied.")
        return

    section = message.text.strip()

    if section == "API Accounts":
        if not await has_permission(user.id, "manage_accounts"):
            await message.reply_text("Is section ki permission nahi hai.")
            return

        await message.reply_text(
            "API Accounts Commands:\n\n"
            "/addapi NAME API_ID API_HASH\n"
            "/apiconfigs\n"
            "/renameapi CONFIG_ID NEW_NAME\n"
            "/activateapi CONFIG_ID\n"
            "/deactivateapi CONFIG_ID\n"
            "/removeapi CONFIG_ID\n\n"
            "API Hash ko sirf private chat mein enter karein."
        )

    elif section == "Channels / Groups":
        if not await has_permission(user.id, "manage_channels"):
            await message.reply_text("Is section ki permission nahi hai.")
            return

        await message.reply_text(
            "Channels / Groups Commands:\n\n"
            "/addchannel @username\n"
            "/addchannel https://t.me/username\n"
            "/channels\n"
            "/activatechannel @username\n"
            "/deactivatechannel @username"
        )

    elif section == "Live Tasks":
        if not await has_permission(user.id, "manage_live"):
            await message.reply_text("Is section ki permission nahi hai.")
            return

        await message.reply_text(
            "Live Task Commands:\n\n"
            "/setlivetarget @username QUANTITY\n"
            "/livetasks\n"
            "/startlive TASK_ID\n"
            "/stoplive TASK_ID\n\n"
            "Note: Ye configuration commands hain; "
            "actual live-stream worker alag se chahiye."
        )

    elif section == "Reaction Tasks":
        if not await has_permission(user.id, "manage_reactions"):
            await message.reply_text("Is section ki permission nahi hai.")
            return

        await message.reply_text(
            "Reaction Task Commands:\n\n"
            "/setreaction @username REACTION QUANTITY\n"
            "/reactiontasks\n"
            "/startreactions TASK_ID\n"
            "/stopreactions TASK_ID\n\n"
            "Note: Ye task configuration aur status manage karte hain."
        )

    elif section == "Reports":
        if not await has_permission(user.id, "view_reports"):
            await message.reply_text("Reports ki permission nahi hai.")
            return

        await message.reply_text(
            "Report Commands:\n\n"
            "/report 24h\n"
            "/report 72h\n"
            "/report daily\n"
            "/report weekly\n"
            "/report monthly\n"
            "/recentactivity"
        )

    elif section == "Admin Help":
        await message.reply_text(
            "Admin Help:\n\n"
            "/start - Main menu\n"
            "/help - Command overview\n\n"
            "Owner-admin permissions aur sub-admin permissions "
            "alag ho sakti hain. API credentials private rakhein."
        )

    else:
        await message.reply_text(
            "Menu mein se koi section select karein ya /start type karein."
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await start(update, context)


def get_start_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
    ]


def get_menu_handlers():
    from telegram.ext import MessageHandler, filters

    return [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_router,
        )
    ]
