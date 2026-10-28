
"""Central command registry and command-list handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID

router = Router(name="commands")


# Commands are grouped by access level and feature.
# "Planned" commands are documented but are not registered here
# until their actual feature handlers have been implemented.

GENERAL_COMMANDS = [
    ("/start", "Bot start karein aur main menu kholein."),
    ("/help", "Bot ke basic use ki help dekhein."),
    ("/cancel", "Current operation cancel karein."),
]

ADMIN_COMMANDS = [
    (
        "/allcommandslist",
        "Sabhi documented commands aur unka kaam dekhein.",
    ),
    ("/users", "Registered users ki list dekhein."),
    ("/channels", "Saved channels ki list dekhein."),
    ("/accounts", "Registered Telegram accounts aur unka status dekhein."),
    ("/reports", "Available reports aur analytics dekhein."),
]

FEATURE_COMMANDS = [
    (
        "/addchannel",
        "Naya channel add karein. Command handler implement hone par active hoga.",
    ),
    (
        "/deactivatechannel",
        "Channel deactivate karein. Command handler implement hone par active hoga.",
    ),
    (
        "/reactivatechannel",
        "Deactivated channel reactivate karein. Command handler implement hone par active hoga.",
    ),
    (
        "/addaccount",
        "Authorized Telegram account connect karne ka workflow shuru karein; implementation pending.",
    ),
    (
        "/accountstatus",
        "Account connection status dekhein; implementation pending.",
    ),
    (
        "/permissions",
        "Admin permissions manage karein; implementation pending.",
    ),
    (
        "/reactions",
        "Channel reaction settings dekhein ya configure karein; implementation pending.",
    ),
    (
        "/monitoring",
        "Monitoring sessions aur unka status dekhein; implementation pending.",
    ),
]


def build_command_list(is_admin: bool) -> str:
    """Build a readable command list for the requesting user."""
    lines = ["📚 <b>Bot Command List</b>", ""]

    lines.append("<b>General Commands</b>")
    for command, description in GENERAL_COMMANDS:
        lines.append(f"<code>{command}</code> — {description}")

    if is_admin:
        lines.extend(["", "<b>Admin Commands</b>"])
        for command, description in ADMIN_COMMANDS:
            lines.append(f"<code>{command}</code> — {description}")

        lines.extend(["", "<b>Feature Commands</b>"])
        for command, description in FEATURE_COMMANDS:
            lines.append(f"<code>{command}</code> — {description}")

        lines.extend(
            [
                "",
                "⚠️ Feature Commands mein kuch commands abhi planned hain. "
                "Unke handlers implement hone ke baad hi woh kaam karengi.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Admin commands ki list dekhne ke liye bot owner se sampark karein.",
            ]
        )

    return "\n".join(lines)


def is_owner(message: Message) -> bool:
    """Check whether the message sender is the configured bot owner."""
    return (
        message.from_user is not None
        and message.from_user.id == OWNER_ID
    )


@router.message(Command("allcommandslist"))
async def all_commands_list_handler(message: Message) -> None:
    """Show the command list; full list is owner-only."""
    await message.answer(
        build_command_list(is_admin=is_owner(message))
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Show basic help."""
    await message.answer(
        "ℹ️ <b>Bot Help</b>\n\n"
        "/start — Main menu kholein.\n"
        "/help — Basic help dekhein.\n"
        "/cancel — Current operation cancel karein.\n"
        "/allcommandslist — Available commands aur unka purpose dekhein."
    )
