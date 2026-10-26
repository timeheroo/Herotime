
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.validators import validate_quantity
from utils.logger import log_action


async def set_live_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Create or update the monitoring target for a channel."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(user.id, "manage_live")
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 2 or not context.args[0].isdigit():
        await message.reply_text(
            "Usage: /setlivetarget CHANNEL_ID QUANTITY\n"
            "Example: /setlivetarget 1 100"
        )
        return

    channel_id = int(context.args[0])

    try:
        quantity = validate_quantity(context.args[1])
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
                "Yeh channel inactive hai. Pehle channel activate karein."
            )
            return

        task_id = await conn.fetchval(
            """
            INSERT INTO live_tasks (
                channel_id, target_quantity, status, created_by
            )
            VALUES ($1, $2, 'stopped', $3)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            channel_id,
            quantity,
            user.id,
        )

        if task_id is None:
            task_id = await conn.fetchval(
                """
                SELECT id FROM live_tasks
                WHERE channel_id = $1
                ORDER BY id DESC
                LIMIT 1
                """,
                channel_id,
            )

            if task_id is None:
                await message.reply_text("Task save nahi ho saka.")
                return

            await conn.execute(
                """
                UPDATE live_tasks
                SET target_quantity = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                task_id,
                quantity,
            )

    await log_action(
        user.id,
        "live_target_updated",
        {
            "task_id": task_id,
            "channel_id": channel_id,
            "target_quantity": quantity,
        },
    )

    await message.reply_text(
        f"✅ Live monitoring target save ho gaya.\n"
        f"Task ID: {task_id}\n"
        f"Channel ID: {channel_id}\n"
        f"Target: {quantity}\n"
        "Status: stopped\n\n"
        "Yeh target setting hai, actual viewer count nahi."
    )


async def list_live_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Display configured live tasks."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(user.id, "manage_live")
    if not allowed:
        await message.reply_text(reason)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        tasks = await conn.fetch(
            """
            SELECT lt.id, lt.channel_id, lt.target_quantity, lt.status,
                   c.username
            FROM live_tasks lt
            JOIN channels c ON c.id = lt.channel_id
            ORDER BY lt.id DESC
            LIMIT 50
            """
        )

    if not tasks:
        await message.reply_text("Abhi koi live task configured nahi hai.")
        return

    lines = ["📺 Live Task Settings"]

    for task in tasks:
        lines.append(
            f"\nTask ID: {task['id']}\n"
            f"Channel: {task['username'] or task['channel_id']}\n"
            f"Target: {task['target_quantity']}\n"
            f"Status: {task['status']}"
        )

    await message.reply_text("\n".join(lines))


async def set_live_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status: str,
) -> None:
    """Set a task's desired status."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(user.id, "manage_live")
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        command = "/startlive" if status == "running" else "/stoplive"
        await message.reply_text(f"Usage: {command} TASK_ID")
        return

    task_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE live_tasks
            SET status = $2, updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            status,
        )

    if result.endswith("0"):
        await message.reply_text("Task ID nahi mila.")
        return

    await log_action(
        user.id,
        "live_task_status_changed",
        {"task_id": task_id, "status": status},
    )

    if status == "running":
        await message.reply_text(
            f"Task {task_id} ka desired status running set hua.\n"
            "Actual monitoring worker abhi connect nahi hua hai."
        )
    else:
        await message.reply_text(
            f"Task {task_id} ka status stopped set hua."
        )


async def start_live(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_live_status(update, context, "running")


async def stop_live(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_live_status(update, context, "stopped")


def get_live_handlers():
    return [
        CommandHandler("setlivetarget", set_live_target),
        CommandHandler("livetasks", list_live_tasks),
        CommandHandler("startlive", start_live),
        CommandHandler("stoplive", stop_live),
    ]
