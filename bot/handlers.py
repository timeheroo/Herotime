
"""Telegram bot handlers for channel management."""

import logging

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


# -------------------- MENUS --------------------

def make_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label) for label in row]
            for row in rows
        ],
        resize_keyboard=True,
    )


def get_main_menu() -> ReplyKeyboardMarkup:
    return make_keyboard([
        ["📡 Channel Management"],
        ["😀 Reaction Management", "👤 Account Management"],
        ["📊 Reports/Analytics"],
        ["🔴 Live Stream Management"],
        ["🔐 Admin Permissions"],
    ])


def get_channel_management_menu() -> ReplyKeyboardMarkup:
    return make_keyboard([
        ["➕ Add Channel", "📋 List Channels"],
        ["⏸️ Deactivate Channel", "▶️ Reactivate Channel"],
        ["⬅️ Back to Main Menu"],
    ])


def get_reaction_menu() -> ReplyKeyboardMarkup:
    return make_keyboard([
        ["📡 Channel Management"],
        ["⬅️ Back to Main Menu"],
    ])


# -------------------- FSM STATES --------------------

class AddChannelStates(StatesGroup):
    title = State()
    username_or_link = State()


class ChannelActionStates(StatesGroup):
    deactivate_id = State()
    reactivate_id = State()


# -------------------- HELPERS --------------------

def is_owner(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == OWNER_ID)


async def ensure_user(message: Message) -> int | None:
    """Register or update the Telegram user and return the database ID."""
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
    status = "Active" if channel.is_active else "Inactive"
    username = f"@{channel.username}" if channel.username else "Not set"
    link = channel.chat_link or "Not set"

    return (
        f"ID: {channel.id}\n"
        f"Title: {channel.title}\n"
        f"Username: {username}\n"
        f"Link: {link}\n"
        f"Status: {status}"
    )


# -------------------- START --------------------

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    try:
        await ensure_user(message)
    except Exception:
        logger.exception("Failed to register Telegram user")

        await message.answer(
            "Database se connect karne mein problem hui. "
            "Please thodi der baad try karein."
        )
        return

    await message.answer(
        "Welcome! Telegram Admin Bot mein aapka swagat hai.",
        reply_markup=get_main_menu(),
    )


# -------------------- MAIN MENU --------------------

@router.message(F.text == "📡 Channel Management")
async def channel_management_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "📡 Channel Management\n\nEk option select karein:",
        reply_markup=get_channel_management_menu(),
    )


@router.message(F.text == "⬅️ Back to Main Menu")
async def back_to_main_menu(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "Main Menu",
        reply_markup=get_main_menu(),
    )


# -------------------- ADD CHANNEL --------------------

@router.message(F.text == "➕ Add Channel")
async def add_channel_start(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
        return

    await state.clear()
    await state.set_state(AddChannelStates.title)

    await message.answer(
        "➕ Add Channel\n\n"
        "Channel ka title bhejein.\n"
        "Example: My Updates Channel\n\n"
        "Cancel karne ke liye /cancel bhejein."
    )


@router.message(AddChannelStates.title, F.text)
async def add_channel_title(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await state.clear()
        await message.answer("⛔ Access denied.")
        return

    title = message.text.strip()

    if not title or len(title) > 255:
        await message.answer(
            "Valid title bhejein (1 se 255 characters)."
        )
        return

    await state.update_data(channel_title=title)
    await state.set_state(AddChannelStates.username_or_link)

    await message.answer(
        "Ab channel ka username ya public link bhejein.\n\n"
        "Examples:\n"
        "@mychannel\n"
        "https://t.me/mychannel\n\n"
        "Agar username/link nahi hai to - bhejein."
    )


@router.message(AddChannelStates.username_or_link, F.text)
async def add_channel_save(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await state.clear()
        await message.answer("⛔ Access denied.")
        return

    value = message.text.strip()
    data = await state.get_data()
    title = data.get("channel_title")

    if not title:
        await state.clear()
        await message.answer(
            "Channel title nahi mila. Please dobara Add Channel karein."
        )
        return

    username = None
    chat_link = None

    if value != "-":
        if value.startswith("@"):
            username = value[1:].strip()
        elif value.startswith("https://t.me/"):
            chat_link = value
            username = value.removeprefix(
                "https://t.me/"
            ).split("/")[0].split("?")[0]
            if not username:
                username = None
        else:
            await message.answer(
                "Username @mychannel format mein ya "
                "https://t.me/mychannel link bhejein. "
                "Agar nahi hai to - bhejein."
            )
            return

    try:
        user_id = await ensure_user(message)

        async with SessionFactory() as session:
            channel = await create_channel(
                session=session,
                title=title,
                username=username,
                chat_link=chat_link,
                chat_type="channel",
                created_by_user_id=user_id,
            )

        await state.clear()

        await message.answer(
            "✅ Channel database mein save ho gaya!\n\n"
            f"{format_channel(channel)}",
            reply_markup=get_channel_management_menu(),
        )

    except Exception:
        logger.exception("Failed to save channel")
        await state.clear()

        await message.answer(
            "❌ Channel save nahi ho saka.\n"
            "Railway logs aur database connection check karein.",
            reply_markup=get_channel_management_menu(),
        )


# -------------------- LIST CHANNELS --------------------

@router.message(F.text == "📋 List Channels")
async def list_channels_handler(message: Message):
    if not is_owner(message):
        await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
        return

    try:
        async with SessionFactory() as session:
            channels = await list_channels(
                session=session,
                active_only=False,
            )

        if not channels:
            await message.answer(
                "Abhi database mein koi channel registered nahi hai.",
                reply_markup=get_channel_management_menu(),
            )
            return

        output = ["📋 Registered Channels\n"]

        for channel in channels:
            output.append(format_channel(channel))
            output.append("--------------------")

        text = "\n".join(output)

        # Telegram messages have a maximum length; send in chunks.
        for start in range(0, len(text), 3500):
            await message.answer(
                text[start:start + 3500],
                reply_markup=get_channel_management_menu(),
            )

    except Exception:
        logger.exception("Failed to list channels")
        await message.answer(
            "❌ Channels load nahi ho sake. Railway logs check karein."
        )


# -------------------- DEACTIVATE CHANNEL --------------------

@router.message(F.text == "⏸️ Deactivate Channel")
async def deactivate_channel_start(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
        return

    await state.clear()
    await state.set_state(ChannelActionStates.deactivate_id)

    await message.answer(
        "Deactivate karne ke liye channel ka database ID bhejein.\n"
        "ID List Channels mein mil jayegi.\n"
        "Cancel: /cancel"
    )


@router.message(ChannelActionStates.deactivate_id, F.text)
async def deactivate_channel_confirm(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await state.clear()
        await message.answer("⛔ Access denied.")
        return

    try:
        channel_id = int(message.text.strip())
        async with SessionFactory() as session:
            success = await deactivate_channel(session, channel_id)

        await state.clear()

        if success:
            await message.answer(
                f"✅ Channel ID {channel_id} deactivate ho gaya.",
                reply_markup=get_channel_management_menu(),
            )
        else:
            await message.answer(
                "❌ Is ID ka channel nahi mila.",
                reply_markup=get_channel_management_menu(),
            )

    except ValueError:
        await message.answer("Sirf numeric channel ID bhejein.")
    except Exception:
        logger.exception("Failed to deactivate channel")
        await state.clear()
        await message.answer("❌ Deactivation fail hua. Logs check karein.")


# -------------------- REACTIVATE CHANNEL --------------------

@router.message(F.text == "▶️ Reactivate Channel")
async def reactivate_channel_start(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
        return

    await state.clear()
    await state.set_state(ChannelActionStates.reactivate_id)

    await message.answer(
        "Reactivate karne ke liye channel ka database ID bhejein.\n"
        "ID List Channels mein mil jayegi.\n"
        "Cancel: /cancel"
    )


@router.message(ChannelActionStates.reactivate_id, F.text)
async def reactivate_channel_confirm(
    message: Message,
    state: FSMContext,
):
    if not is_owner(message):
        await state.clear()
        await message.answer("⛔ Access denied.")
        return

    try:
        channel_id = int(message.text.strip())

        async with SessionFactory() as session:
            channel = await get_channel(session, channel_id)

            if channel is not None:
                channel.is_active = True
                await session.commit()
                await session.refresh(channel)

        await state.clear()

        if channel is None:
            await message.answer(
                "❌ Is ID ka channel nahi mila.",
                reply_markup=get_channel_management_menu(),
            )
        else:
            await message.answer(
                f"✅ Channel ID {channel_id} reactivate ho gaya.",
                reply_markup=get_channel_management_menu(),
            )

    except ValueError:
        await message.answer("Sirf numeric channel ID bhejein.")
    except Exception:
        logger.exception("Failed to reactivate channel")
        await state.clear()
        await message.answer("❌ Reactivation fail hua. Logs check karein.")


# -------------------- CANCEL --------------------

@router.message(F.text == "/cancel")
async def cancel_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "Current action cancel kar diya gaya.",
        reply_markup=get_channel_management_menu(),
    )


# -------------------- OTHER MENU OPTIONS --------------------

@router.message(F.text == "😀 Reaction Management")
async def reaction_management_handler(message: Message):
    await message.answer(
        "Reaction Management abhi connect nahi hua hai.",
        reply_markup=get_reaction_menu(),
    )


@router.message(F.text == "👤 Account Management")
async def account_management_handler(message: Message):
    await message.answer(
        "Account Management abhi connect nahi hua hai.",
        reply_markup=get_main_menu(),
    )


@router.message(F.text == "📊 Reports/Analytics")
async def reports_handler(message: Message):
    await message.answer(
        "Reports/Analytics abhi connect nahi hua hai.",
        reply_markup=get_main_menu(),
    )


@router.message(F.text == "🔴 Live Stream Management")
async def live_stream_handler(message: Message):
    await message.answer(
        "Live Stream Management abhi connect nahi hua hai.",
        reply_markup=get_main_menu(),
    )


@router.message(F.text == "🔐 Admin Permissions")
async def admin_permissions_handler(message: Message):
    if not is_owner(message):
        await message.answer("⛔ Ye action sirf bot owner kar sakta hai.")
        return

    await message.answer(
        "Admin Permissions abhi connect nahi hua hai.",
        reply_markup=get_main_menu(),
    )


# -------------------- REGISTER --------------------

def register_handlers(dispatcher):
    dispatcher.include_router(router)
