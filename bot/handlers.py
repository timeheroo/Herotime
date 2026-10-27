"""Telegram bot handlers and interactive reaction management menus."""

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
KeyboardButton,
Message,
ReplyKeyboardMarkup,
)
from config import OWNER_ID

logger = logging.getLogger(**name**)
router = Router()

MAIN_MENU_BUTTONS = [
"Channel Management",
"Reaction Management",
"Account Management",
"Reports/Analytics",
"Live Stream Management",
"Admin Permissions",
]

REACTION_MENU_BUTTONS = [
"Service Reaction",
"Channel Reaction",
"⬅️ Back to Main Menu",
]

def make_keyboard(
buttons: list[str],
columns: int = 2,
) -> ReplyKeyboardMarkup:
"""Build a reply keyboard with the requested number of columns."""
rows = [
[
KeyboardButton(text=buttons[index])
for index in range(start, min(start + columns, len(buttons)))
]
for start in range(0, len(buttons), columns)
]

```
return ReplyKeyboardMarkup(
    keyboard=rows,
    resize_keyboard=True,
    one_time_keyboard=False,
)
```

def get_main_menu() -> ReplyKeyboardMarkup:
return make_keyboard(MAIN_MENU_BUTTONS, columns=2)

def get_reaction_menu() -> ReplyKeyboardMarkup:
return make_keyboard(REACTION_MENU_BUTTONS, columns=1)

def get_service_reaction_menu() -> ReplyKeyboardMarkup:
return make_keyboard(
[
"📋 List Reaction Accounts",
"⬅️ Back to Reaction Menu",
"🏠 Back to Main Menu",
],
columns=1,
)

def get_channel_reaction_menu() -> ReplyKeyboardMarkup:
return make_keyboard(
[
"📋 List Channels",
"➕ Set Reaction Quantity",
"▶️ Start Reaction Service",
"⏹ Stop Reaction Service",
"⬅️ Back to Reaction Menu",
"🏠 Back to Main Menu",
],
columns=1,
)

@router.message(CommandStart())
async def start_handler(message: Message) -> None:
if message.from_user is None:
return

```
await message.answer(
    "Welcome! Telegram Management Bot is running.\n\n"
    "Choose an option from the menu below.",
    reply_markup=get_main_menu(),
)
```

@router.message(F.text == "Reaction Management")
async def reaction_management_handler(message: Message) -> None:
await message.answer(
"❤️ <b>Reaction Management</b>\n\n"
"Please select an option:",
reply_markup=get_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "Service Reaction")
async def service_reaction_handler(message: Message) -> None:
await message.answer(
"👥 <b>Service Reaction</b>\n\n"
"Yahan registered reaction accounts ki list aur unka status "
"dikhaya jayega.\n\n"
"Abhi account data database se connect nahi hua hai.",
reply_markup=get_service_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "Channel Reaction")
async def channel_reaction_handler(message: Message) -> None:
await message.answer(
"📊 <b>Channel Reaction</b>\n\n"
"Yahan channel-wise reaction quantity aur service controls honge.\n\n"
"Abhi channel data database se connect nahi hua hai.",
reply_markup=get_channel_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "📋 List Reaction Accounts")
async def list_reaction_accounts_handler(message: Message) -> None:
await message.answer(
"📋 <b>Reaction Accounts</b>\n\n"
"Abhi koi account list database se load nahi ki gayi.\n"
"Account Management integration agle step mein hogi.",
parse_mode="HTML",
)

@router.message(F.text == "📋 List Channels")
async def list_reaction_channels_handler(message: Message) -> None:
await message.answer(
"📋 <b>Channel List</b>\n\n"
"Abhi registered channels database se load nahi kiye gaye.\n"
"Channel Management integration agle step mein hogi.",
parse_mode="HTML",
)

@router.message(F.text == "➕ Set Reaction Quantity")
async def set_reaction_quantity_handler(message: Message) -> None:
await message.answer(
"➕ <b>Set Reaction Quantity</b>\n\n"
"Quantity set karne se pehle channel selection aur database "
"integration zaroori hai. Yeh agle step mein implement hoga.",
parse_mode="HTML",
)

@router.message(F.text == "▶️ Start Reaction Service")
async def start_reaction_service_handler(message: Message) -> None:
await message.answer(
"▶️ <b>Start Reaction Service</b>\n\n"
"Service abhi start nahi ki gayi hai. Actual service start "
"karne se pehle channel, configuration aur permissions verify "
"karna zaroori hai.",
parse_mode="HTML",
)

@router.message(F.text == "⏹ Stop Reaction Service")
async def stop_reaction_service_handler(message: Message) -> None:
await message.answer(
"⏹ <b>Stop Reaction Service</b>\n\n"
"Abhi database se koi active service load nahi ki gayi hai.",
parse_mode="HTML",
)

@router.message(F.text == "⬅️ Back to Reaction Menu")
async def back_to_reaction_menu_handler(message: Message) -> None:
await message.answer(
"❤️ Reaction Management\n\nPlease select an option:",
reply_markup=get_reaction_menu(),
)

@router.message(F.text.in_({"🏠 Back to Main Menu", "⬅️ Back to Main Menu"}))
async def back_to_main_menu_handler(message: Message) -> None:
await message.answer(
"🏠 Main Menu\n\nChoose an option:",
reply_markup=get_main_menu(),
)

@router.message(F.text == "Channel Management")
async def channel_management_handler(message: Message) -> None:
await message.answer(
"📢 <b>Channel Management</b>\n\n"
"Channel add/list/remove features abhi implement hone baaki hain.",
parse_mode="HTML",
)

@router.message(F.text == "Account Management")
async def account_management_handler(message: Message) -> None:
await message.answer(
"👤 <b>Account Management</b>\n\n"
"Account registration aur secure credential management "
"abhi implement hone baaki hain.",
parse_mode="HTML",
)

@router.message(F.text == "Reports/Analytics")
async def reports_handler(message: Message) -> None:
await message.answer(
"📈 <b>Reports/Analytics</b>\n\n"
"Reports database integration ke baad available hongi.",
parse_mode="HTML",
)

@router.message(F.text == "Live Stream Management")
async def live_stream_handler(message: Message) -> None:
await message.answer(
"🔴 <b>Live Stream Management</b>\n\n"
"Monitoring controls abhi implement hone baaki hain.",
parse_mode="HTML",
)

@router.message(F.text == "Admin Permissions")
async def admin_permissions_handler(message: Message) -> None:
if message.from_user is None or message.from_user.id != OWNER_ID:
await message.answer("Sorry, only the bot owner can access this menu.")
return

```
await message.answer(
    "🛡️ <b>Admin Permissions</b>\n\n"
    "Admin management aur individual permissions abhi implement "
    "hone baaki hain.",
    parse_mode="HTML",
)
```

async def register_handlers(dispatcher) -> None:
"""Register the bot's message handlers."""
dispatcher.include_router(router)
logger.info("Bot handlers registered.")
