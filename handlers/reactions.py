
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.validators import validate_quantity
from utils.logger import log_action


ALLOWED_REACTIONS = {
    "like",
    "heart",
    "fire",
    "thumbsup",
    "laugh",
    "sad",
    "wow",
}


async def set_reaction_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Save an authorized reaction task's target and reaction preference."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_reactions"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 3:
        await message.reply_text(
            "Usage: /setreaction CHANNEL_ID REACTION QUANTITY\n"
            "Example: /setreaction 1 heart 10\n\n"
            "Supported preferences: "
            + ", ".join(sorted(ALLOWED_REACTIONS))
        )
        return

    if not context.args[0].isdigit():
        await message.reply_text("Channel ID numeric hona chahiye.")
        return

    channel_id = int(context.args[0])
    reaction_type = context.args[1].strip().lower()

    if reaction_type not in ALLOWED_REACTIONS:
        await message.reply_text(
            "Unsupported reaction preference.\n"
            "Options: " + ", ".join(sorted(ALLOWED_REACTIONS))
        )
        return

    try:
        quantity = validate_quantity(context.args[2])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        channel = await conn.fetchrow(
            "SELECT id, is_active FROM channels WHERE id = $1",
            channel_id,
        )

        if channel is None:
            await message.reply_text("Channel ID nahi mila.")
            return

        if not channel["is_active"]:
            await message.reply_text(
                "Channel inactive hai. Pehle use activate karein."
            )
            return

        task_id = await conn.fetchval(
            """
            INSERT INTO reaction_tasks (
                channel_id, reaction_type, target_quantity,
                status, created_by
            )
            VALUES ($1, $2, $3, 'stopped', $4)
            RETURNING id
            """,
            channel_id,
            reaction_type,
            quantity,
            user.id,
        )

    await log_action(
        user.id,
        "reaction_task_created",
        {
            "task_id": task_id,
            "channel_id": channel_id,
            "reaction_type": reaction_type,
            "target_quantity": quantity,
        },
    )

    await message.reply_text(
        f"✅ Reaction preference saved.\n"
        f"Task ID: {task_id}\n"
        f"Channel ID: {channel_id}\n"
        f"Preference: {reaction_type}\n"
        f"Target: {quantity}\n"
        "Status: stopped\n\n"
        "Yeh configuration hai; reactions automatically send nahi hue."
    )


async def list_reaction_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """List reaction task configurations."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_reactions"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        tasks = await conn.fetch(
            """
            SELECT id, channel_id, reaction_type,
                   target_quantity, status
            FROM reaction_tasks
            ORDER BY id DESC
            LIMIT 50
            """
        )

    if not tasks:
        await message.reply_text("Abhi koi reaction task nahi hai.")
        return

    lines = ["💬 Reaction Task Settings"]

    for task in tasks:
        lines.append(
            f"\nTask ID: {task['id']}\n"
            f"Channel ID: {task['channel_id']}\n"
            f"Preference: {task['reaction_type']}\n"
            f"Target: {task['target_quantity']}\n"
            f"Status: {task['status']}"
        )

    await message.reply_text("\n".join(lines))


async def set_reaction_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status: str,
) -> None:
    """Update a reaction task's desired status."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_reactions"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        command = (
            "/startreactions"
            if status == "running"
            else "/stopreactions"
        )
        await message.reply_text(f"Usage: {command} TASK_ID")
        return

    task_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE reaction_tasks
            SET status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            status,
        )

    if result.endswith("0"):
        await message.reply_text("Reaction task ID nahi mila.")
        return

    await log_action(
        user.id,
        "reaction_task_status_changed",
        {"task_id": task_id, "status": status},
    )

    if status == "running":
        await message.reply_text(
            f"Task {task_id} ka desired status running set hua.\n"
            "Actual reaction worker abhi connect nahi hua hai."
        )
    else:
        await message.reply_text(
            f"Task {task_id} stopped mark kar diya gaya."
        )


async def start_reactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_reaction_status(update, context, "running")


async def stop_reactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_reaction_status(update, context, "stopped")


def get_reaction_handlers():
    return [
        CommandHandler("setreaction", set_reaction_target),
        CommandHandler("reactiontasks", list_reaction_tasks),
        CommandHandler("startreactions", start_reactions),
        CommandHandler("stopreactions", stop_reactions),
    ]
