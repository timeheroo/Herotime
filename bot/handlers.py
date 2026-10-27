"""Telegram bot handlers with PostgreSQL channel listing."""

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
KeyboardButton,
Message,
ReplyKeyboardMarkup,
)
from sqlalchemy import select

from config import OWNER_ID
from database.connection import SessionFactory
from database.models import Channel

logger = logging.getLogger(name)
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
"""Create a reply keyboard."""
if columns < 1:
raise ValueError("columns must be at least 1")

rows = [ [ KeyboardButton(text=buttons[index]) for index in range(start, min(start + columns, len(buttons))) ] for start in range(0, len(buttons), columns) ] return ReplyKeyboardMarkup( keyboard=rows, resize_keyboard=True, one_time_keyboard=False, ) 

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

await message.answer( "Welcome! Telegram Management Bot is running.\n\n" "Choose an option from the menu below.", reply_markup=get_main_menu(), ) 

@router.message(F.text == "Reaction Management")
async def reaction_management_handler(message: Message) -> None:
await message.answer(
"❤️ Reaction Management\n\nPlease select an option:",
reply_markup=get_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "Service Reaction")
async def service_reaction_handler(message: Message) -> None:
await message.answer(
"👥 Service Reaction\n\n"
"Reaction accounts ka database listing abhi implement nahi hua hai.",
reply_markup=get_service_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "Channel Reaction")
async def channel_reaction_handler(message: Message) -> None:
await message.answer(
"📊 Channel Reaction\n\n"
"Yahan channel-wise configuration aur service controls honge.",
reply_markup=get_channel_reaction_menu(),
parse_mode="HTML",
)

@router.message(F.text == "📋 List Reaction Accounts")
async def list_reaction_accounts_handler(message: Message) -> None:
await message.answer(
"📋 Reaction Accounts\n\n"
"Account listing abhi implement nahi hui hai.",
parse_mode="HTML",
)

@router.message(F.text == "📋 List Channels")
async def list_reaction_channels_handler(message: Message) -> None:
"""Show active channels stored in PostgreSQL."""
try:
async with SessionFactory() as session:
result = await session.execute(
select(Channel)
.where(Channel.is_active.is_(True))
.order_by(Channel.id.desc())
)
channels = result.scalars().all()

if not channels: await message.answer( "📋 <b>Channel List</b>\n\n" "Database mein abhi koi active channel nahi mila." ) return lines = ["📋 <b>Registered Channels</b>\n"] for channel in channels: username = ( f"@{channel.username.lstrip('@')}" if channel.username else "Not set" ) link = ( f"\n🔗 {channel.chat_link}" if channel.chat_link else "" ) lines.append( f"🆔 ID: <code>{channel.id}</code>\n" f"📌 Name: {channel.title}\n" f"👤 Username: {username}" f"{link}" ) await message.answer( "\n\n".join(lines), parse_mode="HTML", ) except Exception: logger.exception("Could not load channels from PostgreSQL.") await message.answer( "❌ Channels load nahi ho sake. " "Railway deployment logs check karein." ) 

@router.message(F.text == "➕ Set Reaction Quantity")
async def set_reaction_quantity_handler(message: Message) -> None:
await message.answer(
"➕ Set Reaction Quantity\n\n"
"Quantity save karne ke liye agle step mein database workflow "
"add kiya jayega.",
parse_mode="HTML",
)

@router.message(F.text == "▶️ Start Reaction Service")
async def start_reaction_service_handler(message: Message) -> None:
await message.answer(
"▶️ Start Reaction Service\n\n"
"Service abhi start nahi hui hai. Actual service implementation "
"aur permissions verification abhi baaki hain.",
parse_mode="HTML",
)

@router.message(F.text == "⏹ Stop Reaction Service")
async def stop_reaction_service_handler(message: Message) -> None:
await message.answer(
"⏹ Stop Reaction Service\n\n"
"Service status integration abhi implement nahi hui hai.",
parse_mode="HTML",
)

@router.message(F.text == "⬅️ Back to Reaction Menu")
async def back_to_reaction_menu_handler(message: Message) -> None:
await message.answer(
"❤️ Reaction Management\n\nPlease select an option:",
reply_markup=get_reaction_menu(),
)

@router.message(
F.text.in_({"🏠 Back to Main Menu", "⬅️ Back to Main Menu"})
)
async def back_to_main_menu_handler(message: Message) -> None:
await message.answer(
"🏠 Main Menu\n\nChoose an option:",
reply_markup=get_main_menu(),
)

@router.message(F.text == "Channel Management")
async def channel_management_handler(message: Message) -> None:
await message.answer(
"📢 Channel Management\n\n"
"Channel add/remove workflow agle step mein implement hoga.",
parse_mode="HTML",
)

@router.message(F.text == "Account Management")
async def account_management_handler(message: Message) -> None:
await message.answer(
"👤 Account Management\n\n"
"Account registration aur secure credential management "
"abhi implement nahi hue hain.",
parse_mode="HTML",
)

@router.message(F.text == "Reports/Analytics")
async def reports_handler(message: Message) -> None:
await message.answer(
"📈 Reports/Analytics\n\n"
"Reports integration agle step mein implement hogi.",
parse_mode="HTML",
)

@router.message(F.text == "Live Stream Management")
async def live_stream_handler(message: Message) -> None:
await message.answer(
"🔴 Live Stream Management\n\n"
"Monitoring integration abhi implement nahi hui hai.",
parse_mode="HTML",
)

@router.message(F.text == "Admin Permissions")
async def admin_permissions_handler(message: Message) -> None:
if message.from_user is None or message.from_user.id != OWNER_ID:
await message.answer(
"Sorry, only the bot owner can access this menu."
)
return

await message.answer( "🛡️ <b>Admin Permissions</b>\n\n" "Admin management aur individual permissions agle step mein " "implement hongi.", parse_mode="HTML", ) 

async def register_handlers(dispatcher) -> None:
"""Register bot handlers."""
dispatcher.include_router(router)
logger.info("Bot handlers registered.")

