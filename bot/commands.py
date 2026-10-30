
"""Central command registry and command-list handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID

router = Router(name="commands")


# Only commands with implemented handlers are listed as available.
GENERAL_COMMANDS = [
    ("/start", "Bot start karein aur main menu kholein."),
    ("/help", "Bot ke basic use ki help dekhein."),
    ("/cancel", "Current operation cancel karein."),
    (
        "/allcommandslist",
        "Available commands aur unka kaam dekhein.",
    ),
]


def is_owner(message: Message) -> bool:
    """Check whether the message sender is the configured bot owner."""
    return (
        message.from_user is not None
        and message.from_user.id == OWNER_ID
    )


def build_command_list(is_admin: bool) -> str:
    """Build a command list containing only implemented commands."""
    lines = [
        "📚 <b>Bot Command List</b>",
        "",
        "<b>Available Commands</b>",
    ]

    for command, description in GENERAL_COMMANDS:
        lines.append(
            f"<code>{command}</code> — {description}"
        )

    if is_admin:
        lines.extend(
            [
                "",
                "👑 <b>Owner Access</b>",
                "Owner ke liye main menu mein management options available hain.",
                "",
                "⚠️ Additional admin commands abhi implement nahi hue hain.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Management permissions ke liye bot owner se sampark karein.",
            ]
        )

    return "\n".join(lines)


@router.message(Command("allcommandslist"))
async def all_commands_list_handler(
    message: Message,
) -> None:
    """Show available commands."""
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
        "/allcommandslist — Available commands aur unka purpose dekhein.\n\n"
        "Menu ke buttons se management sections open karein."
    )
