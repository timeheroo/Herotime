
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action


async def set_live_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(user.id, "manage_live")
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage: /setlivetarget CHANNEL_RECORD_ID QUANTITY"
        )
        return

    if not context.args[0].isdigit() or not context.args[1].isdigit():
        await message.reply_text("Dono values positive integer honi chahiye.")
        return

    channel_id = int(context.args[0])
    quantity = int(context.args[1])

    if quantity < 0 or quantity > 1_000_000:
        await message.reply_text("Quantity 0 se 1000000 ke beech rakhein.")
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        channel = await conn.fetchrow(
            """
            SELECT id, title, username
            FROM channels
            WHERE id = $1 AND is_active = TRUE
            """,
            channel_id,
        )

        if channel is None:
            await message.reply_text(
                "Active channel record nahi mila. /channels se ID check karein."
            )
            return

        task_id = await conn.fetchval(
            """
            INSERT INTO live_tasks (
                channel_id, target_quantity, status, created_by
            )
            VALUES ($1, $2, 'stopped', $3)
            RETURNING id
            """,
            channel_id,
            quantity,
            user.id,
        )

    await log_action(
        user.id,
        "live_task_created",
        {
            "task_id": task_id,
            "channel_id": channel_id,
            "target_quantity": quantity,
        },
    )

    await message.reply_text(
        "✅ Live task record created.\n\n"
        f"Task ID: {task_id}\n"
        f"Channel ID: {channel_id}\n"
        f"Target setting: {quantity}\n"
        "Status: stopped\n\n"
        "Note: Yeh configuration record hai. Isse actual viewers ya "
        "live stream start nahi hoti."
    )


async def list_live_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            SELECT t.id, t.channel_id, t.target_quantity,
                   t.status, t.created_at, c.username, c.title,
                   c.is_active
            FROM live_tasks t
            JOIN channels c ON c.id = t.channel_id
            ORDER BY t.id DESC
            LIMIT 30
            """
        )

    if not tasks:
        await message.reply_text("Abhi koi live task record nahi hai.")
        return

    lines = ["🔴 Live Task Records — Latest 30"]

    for task in tasks:
        channel_name = (
            f"@{task['username']}"
            if task["username"]
            else task["title"] or f"Channel {task['channel_id']}"
        )
        channel_status = "active" if task["is_active"] else "inactive"

        lines.append(
            f"\nTask ID: {task['id']}\n"
            f"Channel: {channel_name}\n"
            f"Channel status: {channel_status}\n"
            f"Target setting: {task['target_quantity']}\n"
            f"Task status: {task['status']}"
        )

    await message.reply_text("\n".join(lines))


async def set_live_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status: str,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(user.id, "manage_live")
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        command = "startlive" if status == "running" else "stoplive"
        await message.reply_text(f"Usage: /{command} TASK_ID")
        return

    task_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        if status == "running":
            task = await conn.fetchrow(
                """
                SELECT t.id, t.channel_id, c.is_active
                FROM live_tasks t
                JOIN channels c ON c.id = t.channel_id
                WHERE t.id = $1
                """,
                task_id,
            )

            if task is None:
                await message.reply_text("Live task nahi mila.")
                return

            if not task["is_active"]:
                await message.reply_text(
                    "Channel inactive hai. Pehle channel activate karein."
                )
                return

        row = await conn.fetchrow(
            """
            UPDATE live_tasks
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, channel_id, target_quantity, status
            """,
            status,
            task_id,
        )

    if row is None:
        await message.reply_text("Live task nahi mila.")
        return

    await log_action(
        user.id,
        "live_task_status_changed",
        {"task_id": task_id, "status": status},
    )

    await message.reply_text(
        f"✅ Task record update ho gaya.\n"
        f"Task ID: {row['id']}\n"
        f"Channel ID: {row['channel_id']}\n"
        f"Target setting: {row['target_quantity']}\n"
        f"Status: {row['status']}\n\n"
        "Note: Actual live-stream monitoring worker abhi is code se "
        "start nahi hota."
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
