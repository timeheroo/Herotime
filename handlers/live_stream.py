```python
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import has_permission
from utils.logger import log_action

logger = logging.getLogger(__name__)


async def set_live_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_live"):
        await message.reply_text(
            "❌ Aapko live-task manage karne ki permission nahi hai."
        )
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Use:\n/setlivetarget CHANNEL_ID QUANTITY\n\n"
            "Example:\n/setlivetarget 1 100"
        )
        return

    try:
        channel_id = int(context.args[0])
        quantity = int(context.args[1])

        if channel_id <= 0 or quantity <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text(
            "❌ Channel ID aur quantity positive whole numbers hone chahiye."
        )
        return

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            channel = await conn.fetchrow(
                "SELECT id, title, is_active FROM channels WHERE id = $1",
                channel_id,
            )

            if not channel:
                await message.reply_text(
                    "❌ Channel ID nahi mila. Pehle /channels check karein."
                )
                return

            if not channel["is_active"]:
                await message.reply_text(
                    "❌ Yeh channel inactive hai. Pehle channel activate karein."
                )
                return

            task = await conn.fetchrow(
                """
                INSERT INTO live_tasks (channel_id, target_quantity, status)
                VALUES ($1, $2, 'stopped')
                RETURNING id
                """,
                channel_id,
                quantity,
            )

        await log_action(
            user.id,
            "create_live_task",
            {
                "task_id": task["id"],
                "channel_id": channel_id,
                "quantity": quantity,
            },
        )

        await message.reply_text(
            "✅ Live task configuration create ho gayi.\n"
            f"Task ID: {task['id']}\n"
            f"Channel: {channel['title']}\n"
            f"Target quantity: {quantity}\n"
            "Status: stopped"
        )

    except Exception:
        logger.exception("Failed to create live task")
        await message.reply_text(
            "❌ Task create nahi hua. Database schema aur Railway logs check karein."
        )


async def list_live_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_live"):
        await message.reply_text(
            "❌ Aapko live tasks dekhne ki permission nahi hai."
        )
        return

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.id, t.channel_id, t.target_quantity, t.status,
                       c.title
                FROM live_tasks AS t
                LEFT JOIN channels AS c ON c.id = t.channel_id
                ORDER BY t.id DESC
                """
            )

        if not rows:
            await message.reply_text("Abhi koi live task configuration nahi hai.")
            return

        lines = ["📋 LIVE TASKS", ""]

        for row in rows:
            lines.append(
                f"Task ID: {row['id']}\n"
                f"Channel: {row['title'] or row['channel_id']}\n"
                f"Target: {row['target_quantity']}\n"
                f"Status: {row['status']}\n"
            )

        await message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Failed to list live tasks")
        await message.reply_text("❌ Live task list load nahi hui.")


async def change_live_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    start: bool,
):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_live"):
        await message.reply_text(
            "❌ Aapko live tasks manage karne ki permission nahi hai."
        )
        return

    if len(context.args) != 1:
        command = "startlive" if start else "stoplive"
        await message.reply_text(
            f"Use:\n/{command} TASK_ID\n\nExample:\n/{command} 1"
        )
        return

    try:
        task_id = int(context.args[0])
        if task_id <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Task ID positive whole number hona chahiye.")
        return

    new_status = "running" if start else "stopped"

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            task = await conn.fetchrow(
                """
                UPDATE live_tasks
                SET status = $1
                WHERE id = $2
                RETURNING id, channel_id, target_quantity, status
                """,
                new_status,
                task_id,
            )

        if not task:
            await message.reply_text("❌ Is ID ka live task nahi mila.")
            return

        await log_action(
            user.id,
            "start_live_task" if start else "stop_live_task",
            {"task_id": task_id, "status": new_status},
        )

        await message.reply_text(
            f"✅ Task status update ho gaya.\n"
            f"Task ID: {task['id']}\n"
            f"Status: {task['status']}"
        )

    except Exception:
        logger.exception("Failed to change live task status")
        await message.reply_text("❌ Task status update nahi hua.")


async def start_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await change_live_status(update, context, True)


async def stop_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await change_live_status(update, context, False)


def get_live_handlers():
    return [
        CommandHandler("setlivetarget", set_live_target),
        CommandHandler("livetasks", list_live_tasks),
        CommandHandler("startlive", start_live),
        CommandHandler("stoplive", stop_live),
    ]
```
