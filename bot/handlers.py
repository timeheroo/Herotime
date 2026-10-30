"""Telegram Management System handlers.

Implements the seven-button menu, submenu navigation, database-backed channel
CRUD already supported by the repository, and interactive quantity/duration
configuration screens. Quantity/duration values in this version are temporary
FSM settings (not persisted to PostgreSQL yet).

No artificial/bulk reactions or coordinated fake livestream viewers are
implemented. Configured targets are not represented as actual activity.
"""

import logging
import re
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from config import OWNER_ID
from database.connection import SessionFactory
from database.repositories import (
    create_channel,
    create_user,
    deactivate_channel,
    get_channel,
    list_channels,
)

logger = logging.getLogger(__name__)
router = Router()

# Main menu labels
CHANNEL = "📡 Channel Management"
REACTION = "😀 Reaction Management"
ACCOUNT = "👤 Account Management"
REPORTS = "📊 Reports/Analytics"
LIVE = "🔴 Live Stream Management"
ADMIN = "🔐 Admin Permissions"
BOT_REACTION = "🤖 BOT REACTION"
BACK_MAIN = "⬅️ Back to Main Menu"
BACK = "⬅️ Back"

# Channel labels
ADD_CHANNEL = "➕ Add Channel"
LIST_CHANNELS = "📋 List Channels"
DEACTIVATE_CHANNEL = "⏸️ Deactivate Channel"
REACTIVATE_CHANNEL = "▶️ Reactivate Channel"

# Exact requested submenu labels
CHANNEL_REACTION = "CHANNEL REACTION"
ACCOUNT_REACTION = "ACCOUNT REACTION"
CHANNELS_REPORT = "CHANNELS REPORT"
LIVE_REPORT = "LIVE STREAM REPORT"
REACTION_REPORT = "REACTION REPORT"
LIVE_ACCOUNT = "LIVE STREAM ACCOUNT"
LIVE_CHANNEL = "LIVE STREAM CHANNEL"

# Common quantity/duration controls
SET_QUANTITY = "🔢 Set Quantity"
INCREASE_QUANTITY = "➕ Increase Quantity"
DECREASE_QUANTITY = "➖ Decrease Quantity"
CUSTOMISE = "⚙️ Customise Settings"
DURATION = "⏱️ Set Duration"
DURATIONS = ["24 Hours", "72 Hours", "1 Week", "1 Month"]


def keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=value) for value in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder="Select an option",
    )


def main_menu():
    return keyboard([
        [CHANNEL],
        [REACTION, ACCOUNT],
        [REPORTS],
        [LIVE],
        [BOT_REACTION],
        [ADMIN],
    ])


def channel_menu():
    return keyboard([
        [ADD_CHANNEL, LIST_CHANNELS],
        [DEACTIVATE_CHANNEL, REACTIVATE_CHANNEL],
        [BACK_MAIN],
    ])


def reaction_menu():
    return keyboard([[CHANNEL_REACTION], [ACCOUNT_REACTION], [BACK_MAIN]])


def account_menu():
    return keyboard([
        ["➕ Add API Account", "📋 List API Accounts"],
        ["✏️ Rename API Account", "🗑️ Remove API Account"],
        [BACK_MAIN],
    ])


def channel_reaction_menu():
    return keyboard([
        ["📋 List Reaction Channels"],
        [SET_QUANTITY, INCREASE_QUANTITY, DECREASE_QUANTITY],
        [CUSTOMISE, DURATION],
        ["▶️ Start Reaction Monitoring", "⏹ Stop Reaction Monitoring"],
        [BACK, BACK_MAIN],
    ])


def account_reaction_menu():
    return keyboard([
        ["📋 List Reaction Accounts"],
        [SET_QUANTITY, INCREASE_QUANTITY, DECREASE_QUANTITY],
        [CUSTOMISE, DURATION],
        [BACK, BACK_MAIN],
    ])


def reports_menu():
    return keyboard([[CHANNELS_REPORT], [BACK_MAIN]])


def channels_report_menu():
    return keyboard([[LIVE_REPORT], [REACTION_REPORT], [BACK, BACK_MAIN]])


def live_menu():
    return keyboard([
        [LIVE_ACCOUNT],
        [LIVE_CHANNEL],
        [BACK_MAIN],
    ])


def live_account_menu():
    return keyboard([[BACK, BACK_MAIN]])


def live_channel_menu():
    return keyboard([
        [SET_QUANTITY, INCREASE_QUANTITY, DECREASE_QUANTITY],
        [CUSTOMISE, DURATION],
        ["▶️ Start Monitoring", "⏹ Stop Monitoring"],
        [BACK, BACK_MAIN],
    ])


def bot_reaction_menu():
    return keyboard([
        ["➕ Add Bot Token", "📋 List Added Bots"],
        ["✏️ Rename Bot", "🗑️ Remove Bot"],
        ["🔍 Check Bot Status"],
        [SET_QUANTITY, INCREASE_QUANTITY, DECREASE_QUANTITY],
        [CUSTOMISE, DURATION],
        ["📡 Channel / Group Monitoring", "📊 Bot Reaction Reports"],
        [BACK_MAIN],
    ])


def admin_menu():
    return keyboard([
        ["➕ Promote Admin", "📋 List Admins"],
        ["⚙️ Admin Permissions"],
        [BACK_MAIN],
    ])


class AddChannel(StatesGroup):
    title = State()
    username_or_link = State()


class ChannelAction(StatesGroup):
    deactivate_id = State()
    reactivate_id = State()


class QuantityConfig(StatesGroup):
    set_value = State()
    increase_value = State()
    decrease_value = State()


async def is_owner(message: Message) -> bool:
    if message.from_user and message.from_user.id == OWNER_ID:
        return True
    await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
    return False


async def ensure_user(message: Message) -> Optional[int]:
    if not message.from_user:
        return None
    async with SessionFactory() as session:
        user = await create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            display_name=message.from_user.full_name,
        )
        return user.id


def format_channel(channel) -> str:
    return (
        f"ID: {channel.id}\n"
        f"Title: {channel.title}\n"
        f"Username: @{channel.username if channel.username else 'Not set'}\n"
        f"Link: {channel.chat_link or 'Not set'}\n"
        f"Status: {'Active' if channel.is_active else 'Inactive'}"
    )


async def show(message: Message, text: str, markup: ReplyKeyboardMarkup):
    await message.answer(text, reply_markup=markup)


# -------------------- START AND BACK NAVIGATION --------------------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    try:
        await ensure_user(message)
    except Exception:
        logger.exception("Could not register user")
        await message.answer("Database connection error. Railway logs check karein.")
        return
    await show(message, "Welcome to Telegram Management System.\nMain menu select karein:", main_menu())


@router.message(F.text == BACK_MAIN)
async def go_main(message: Message, state: FSMContext):
    await state.clear()
    await show(message, "Main Menu", main_menu())


@router.message(F.text == BACK)
async def go_back(message: Message, state: FSMContext):
    data = await state.get_data()
    parent = data.get("parent")
    await state.clear()
    if parent == "reaction":
        await show(message, "Reaction Management", reaction_menu())
    elif parent == "reports":
        await show(message, "Reports", reports_menu())
    elif parent == "live":
        await show(message, "Live Stream Management", live_menu())
    elif parent == "bot_reaction":
        await show(message, "BOT REACTION", bot_reaction_menu())
    else:
        await show(message, "Main Menu", main_menu())


# -------------------- SEVEN MAIN SECTIONS --------------------

@router.message(F.text == CHANNEL)
async def open_channel(message: Message, state: FSMContext):
    await state.clear()
    await show(message, "📡 Channel Management", channel_menu())


@router.message(F.text == REACTION)
async def open_reaction(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="reaction")
    await show(message, "Reaction Management", reaction_menu())


@router.message(F.text == ACCOUNT)
async def open_account(message: Message, state: FSMContext):
    await state.clear()
    await show(message, "Account Management\nAPI ID/API Hash account controls:", account_menu())


@router.message(F.text == REPORTS)
async def open_reports(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="reports")
    await show(message, "Reports/Analytics", reports_menu())


@router.message(F.text == LIVE)
async def open_live(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="live")
    await show(message, "Live Stream Management", live_menu())


@router.message(F.text == BOT_REACTION)
async def open_bot_reaction(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="bot_reaction")
    await show(message, "🤖 BOT REACTION\nBot token management and permitted monitoring:", bot_reaction_menu())


@router.message(F.text == ADMIN)
async def open_admin(message: Message, state: FSMContext):
    await state.clear()
    if not await is_owner(message):
        return
    await show(message, "Admin Permissions", admin_menu())


# -------------------- CHANNEL CRUD (EXISTING DB FUNCTIONS) --------------------

@router.message(F.text == ADD_CHANNEL)
async def add_channel_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.clear()
    await state.set_state(AddChannel.title)
    await message.answer("Channel title bhejein. Cancel: /cancel")


@router.message(AddChannel.title, F.text)
async def add_channel_title(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    title = message.text.strip()
    if not title or len(title) > 255:
        await message.answer("Title 1–255 characters ka hona chahiye.")
        return
    await state.update_data(channel_title=title)
    await state.set_state(AddChannel.username_or_link)
    await message.answer("Channel @username ya https://t.me/ link bhejein. Nahi hai to - bhejein.")


@router.message(AddChannel.username_or_link, F.text)
async def add_channel_save(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    value = message.text.strip()
    data = await state.get_data()
    title = data.get("channel_title")
    username = None
    link = None

    if value != "-":
        if value.startswith("@"):
            username = value[1:].strip()
        elif value.startswith("https://t.me/"):
            link = value
            username = value.removeprefix("https://t.me/").split("/")[0].split("?")[0]
        else:
            await message.answer("Valid @username/link bhejein, ya - bhejein.")
            return
        if not username or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            await message.answer("Telegram public username valid nahi hai.")
            return

    try:
        owner_user_id = await ensure_user(message)
        if owner_user_id is None or not title:
            raise RuntimeError("Missing user or channel title")
        async with SessionFactory() as session:
            channel = await create_channel(
                session=session,
                title=title,
                username=username,
                chat_link=link,
                chat_type="channel",
                created_by_user_id=owner_user_id,
            )
        await state.clear()
        await show(message, "✅ Channel database mein save ho gaya.\n\n" + format_channel(channel), channel_menu())
    except Exception:
        logger.exception("Could not create channel")
        await state.clear()
        await show(message, "❌ Channel save nahi hua. Duplicate username/database error ho sakta hai.", channel_menu())


@router.message(F.text == LIST_CHANNELS)
async def list_channels_handler(message: Message):
    if not await is_owner(message):
        return
    try:
        async with SessionFactory() as session:
            channels = await list_channels(session=session, active_only=False)
        if not channels:
            await show(message, "Abhi koi channel registered nahi hai.", channel_menu())
            return
        text = "📋 Registered Channels\n\n" + "\n\n────────────\n\n".join(format_channel(c) for c in channels)
        for index in range(0, len(text), 3500):
            await message.answer(text[index:index + 3500], reply_markup=channel_menu())
    except Exception:
        logger.exception("Could not list channels")
        await message.answer("❌ Channels load nahi hue. Railway logs check karein.")


@router.message(F.text == DEACTIVATE_CHANNEL)
async def deactivate_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.clear()
    await state.set_state(ChannelAction.deactivate_id)
    await message.answer("Deactivate karne ke liye channel database ID bhejein. Cancel: /cancel")


@router.message(ChannelAction.deactivate_id, F.text)
async def deactivate_finish(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    try:
        channel_id = int(message.text.strip())
        async with SessionFactory() as session:
            success = await deactivate_channel(session, channel_id)
        await state.clear()
        await show(message, f"✅ Channel {channel_id} deactivate ho gaya." if success else "❌ Channel ID nahi mila.", channel_menu())
    except ValueError:
        await message.answer("Numeric channel ID bhejein.")
    except Exception:
        logger.exception("Deactivate failed")
        await state.clear()
        await show(message, "❌ Deactivation fail hua.", channel_menu())


@router.message(F.text == REACTIVATE_CHANNEL)
async def reactivate_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.clear()
    await state.set_state(ChannelAction.reactivate_id)
    await message.answer("Reactivate karne ke liye channel database ID bhejein. Cancel: /cancel")


@router.message(ChannelAction.reactivate_id, F.text)
async def reactivate_finish(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    try:
        channel_id = int(message.text.strip())
        async with SessionFactory() as session:
            channel = await get_channel(session, channel_id)
            if channel:
                channel.is_active = True
                await session.commit()
                await session.refresh(channel)
        await state.clear()
        await show(message, f"✅ Channel {channel_id} reactivate ho gaya." if channel else "❌ Channel ID nahi mila.", channel_menu())
    except ValueError:
        await message.answer("Numeric channel ID bhejein.")
    except Exception:
        logger.exception("Reactivate failed")
        await state.clear()
        await show(message, "❌ Reactivation fail hua.", channel_menu())


# -------------------- REACTION MENUS --------------------

@router.message(F.text == CHANNEL_REACTION)
async def channel_reaction_open(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="reaction", config_scope="channel_reaction")
    await show(message, "CHANNEL REACTION\nQuantity/duration configuration aur genuine activity monitoring:", channel_reaction_menu())


@router.message(F.text == ACCOUNT_REACTION)
async def account_reaction_open(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="reaction", config_scope="account_reaction")
    await show(message, "ACCOUNT REACTION\nAccount-specific configuration and status:", account_reaction_menu())


# -------------------- LIVE STREAM MENUS --------------------

@router.message(F.text == LIVE_ACCOUNT)
async def live_account_open(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="live", config_scope="live_account")
    await show(message, "LIVE STREAM ACCOUNT\nAuthorized account status/eligibility screen. Artificial bulk joining is not provided.", live_account_menu())


@router.message(F.text == LIVE_CHANNEL)
async def live_channel_open(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="live", config_scope="live_channel")
    await show(message, "LIVE STREAM CHANNEL\nMonitoring target configuration:", live_channel_menu())


# -------------------- BOT REACTION SUBMENUS --------------------

@router.message(F.text.in_({"➕ Add Bot Token", "📋 List Added Bots", "✏️ Rename Bot", "🗑️ Remove Bot", "🔍 Check Bot Status"}))
async def bot_token_action(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.update_data(parent="bot_reaction", config_scope="bot_reaction")
    await message.answer(
        "Bot-token management workflow abhi secure encrypted token repository se connect nahi hua.\n"
        "Token ko chat mein abhi send na karein. Agle step mein encrypted storage aur Bot API validation add karenge.",
        reply_markup=bot_reaction_menu(),
    )


@router.message(F.text.in_({"📡 Channel / Group Monitoring", "📊 Bot Reaction Reports"}))
async def bot_monitoring_action(message: Message):
    await message.answer(
        "Monitoring/report screen selected. Actual collector abhi connect nahi hai; "
        "isliye koi fabricated activity ya reaction count nahi dikhaya jayega."
    )


# -------------------- QUANTITY AND DURATION CONFIGURATION --------------------

CONFIG_BUTTONS = {SET_QUANTITY, INCREASE_QUANTITY, DECREASE_QUANTITY, CUSTOMISE, DURATION}


@router.message(F.text == SET_QUANTITY)
async def quantity_set_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.set_state(QuantityConfig.set_value)
    await message.answer("Target quantity (0 se 100000) bhejein.")


@router.message(F.text == INCREASE_QUANTITY)
async def quantity_increase_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.set_state(QuantityConfig.increase_value)
    await message.answer("Quantity kitni increase karni hai? Positive number bhejein.")


@router.message(F.text == DECREASE_QUANTITY)
async def quantity_decrease_start(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.set_state(QuantityConfig.decrease_value)
    await message.answer("Quantity kitni decrease karni hai? Positive number bhejein.")


async def save_temporary_quantity(message: Message, state: FSMContext, operation: str):
    try:
        value = int(message.text.strip())
        if value < 0 or value > 100000:
            raise ValueError
        data = await state.get_data()
        current = int(data.get("configured_quantity", 0))
        if operation == "set":
            updated = value
        elif operation == "increase":
            updated = current + value
        else:
            updated = current - value
        if updated < 0 or updated > 100000:
            await message.answer("Result 0 se 100000 ke beech hona chahiye. Dobara value bhejein.")
            return
        await state.update_data(configured_quantity=updated)
        await state.set_state(None)
        await message.answer(
            f"Configured target quantity: {updated}\n\n"
            "Note: Ye abhi temporary FSM setting hai; PostgreSQL mein save nahi hui. "
            "Ye actual reactions/viewers ki count nahi hai."
        )
    except ValueError:
        await message.answer("Valid whole number 0–100000 bhejein.")


@router.message(QuantityConfig.set_value, F.text)
async def quantity_set_finish(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    await save_temporary_quantity(message, state, "set")


@router.message(QuantityConfig.increase_value, F.text)
async def quantity_increase_finish(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    await save_temporary_quantity(message, state, "increase")


@router.message(QuantityConfig.decrease_value, F.text)
async def quantity_decrease_finish(message: Message, state: FSMContext):
    if not await is_owner(message):
        await state.clear()
        return
    await save_temporary_quantity(message, state, "decrease")


@router.message(F.text == DURATION)
async def duration_select(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await message.answer(
        "Service duration select karein:",
        reply_markup=keyboard([[DURATIONS[0], DURATIONS[1]], [DURATIONS[2], DURATIONS[3]], [BACK_MAIN]]),
    )


@router.message(F.text.in_(set(DURATIONS)))
async def duration_save(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    await state.update_data(configured_duration=message.text)
    data = await state.get_data()
    scope = data.get("config_scope", "not selected")
    await message.answer(
        f"Selected duration: {message.text}\nSection: {scope}\n\n"
        "Note: Duration abhi temporary FSM setting hai; PostgreSQL mein save nahi hui "
        "aur koi background service start nahi hui."
    )


@router.message(F.text == CUSTOMISE)
async def customise_screen(message: Message, state: FSMContext):
    if not await is_owner(message):
        return
    data = await state.get_data()
    await message.answer(
        "Customise Settings\n"
        f"Current temporary quantity: {data.get('configured_quantity', 'Not set')}\n"
        f"Current temporary duration: {data.get('configured_duration', 'Not set')}\n\n"
        "Quantity aur duration buttons se values set karein. Persistent database save next integration step hai."
    )


# -------------------- REPORTS --------------------

@router.message(F.text == CHANNELS_REPORT)
async def channels_report_open(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(parent="reports")
    await show(message, "CHANNELS REPORT\nReport type select karein:", channels_report_menu())


@router.message(F.text == LIVE_REPORT)
async def live_report(message: Message):
    await message.answer(
        "LIVE STREAM REPORT\nHistorical report screen. Configured targets aur verified "
        "observations alag rakhe jayenge. Live data collector abhi connected nahi hai."
    )


@router.message(F.text == REACTION_REPORT)
async def reaction_report(message: Message):
    await message.answer(
        "REACTION REPORT\nHistorical report screen. Configured quantities aur naturally "
        "observed reactions alag rakhe jayenge. Collector abhi connected nahi hai."
    )


# -------------------- ACCOUNT / ADMIN ACTIONS (NOT YET CONNECTED) --------------------

@router.message(F.text.in_({"➕ Add API Account", "📋 List API Accounts", "✏️ Rename API Account", "🗑️ Remove API Account"}))
async def account_action(message: Message):
    if not await is_owner(message):
        return
    await message.answer(
        "API account workflow abhi secure encrypted session storage se connected nahi hai. "
        "API Hash, session string, OTP ya login code chat mein share na karein."
    )


@router.message(F.text.in_({"➕ Promote Admin", "📋 List Admins", "⚙️ Admin Permissions"}))
async def admin_action(message: Message):
    if not await is_owner(message):
        return
    await message.answer("Admin promotion/permission database workflow abhi connect nahi hua hai.")


@router.message(F.text.in_({
    "📋 List Reaction Channels", "▶️ Start Reaction Monitoring",
    "⏹ Stop Reaction Monitoring", "📋 List Reaction Accounts",
    "⚙️ Account Reaction Settings", "▶️ Start Monitoring", "⏹ Stop Monitoring",
}))
async def service_action_not_connected(message: Message):
    await message.answer(
        "Ye action abhi database/worker se connected nahi hai. Koi service start/stop nahi hui."
    )


# -------------------- CANCEL / FALLBACK --------------------

@router.message(F.text == "/cancel")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await show(message, "Action cancel kar diya gaya.", main_menu())


@router.message()
async def fallback(message: Message):
    if message.text and not message.text.startswith("/"):
        await show(message, "Menu button select karein ya /start bhejein.", main_menu())


def register_handlers(dispatcher):
    dispatcher.include_router(router)
