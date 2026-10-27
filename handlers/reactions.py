
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from database import get_pool
from utils.permissions import require_permission
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


async def set_reaction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    allowed, message = await require_permission(
        user_id, "manage_reactions"
    )
    if not allowed:
        await update.message.reply_text(message)
        return

    if len(context.args) != 3:
        await update.message.reply_text(
            "Usage:\n"
            "/setreaction CHANNEL_ID REACTION QUANTITY\n\n"
            "Example:\n"
            "/setreaction 1 heart 100\n\n"
            "Allowed reactions: "
            + ", ".join(sorted(ALLOWED_REACTIONS))
        )
        return

    try:
        channel_id = int(context.args[0])
        reaction_type = context.args[1].lower()
        quantity = int(context.args[2])
    except ValueError:
        await update.message.reply_text(
            "Channel ID aur quantity number mein honi chahiye."
        )
        return

    if reaction_type not in ALLOWED_REACTIONS:
        await update.message.reply_text(
            "Invalid reaction type.\nAllowed: "
            + ", ".join(sorted(ALLOWED_REACTIONS))
        )
        return

    if quantity < 0 or quantity > 1_000_000:
        await update.message.reply_text(
            "Quantity 0 se 1,000,000 ke beech honi chahiye."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        channel = await conn.fetchrow(
            """
            SELECT id, title, is_active
            FROM channels
            WHERE id = $1
            """,
            channel_id,
        )

        if not channel:
            await update.message.reply_text(
                "Channel record nahi mila. /channels check karein."
            )
            return

        if not channel["is_active"]:
            await update.message.reply_text(
                "Yeh channel inactive hai. Pehle channel activate karein."
            )
            return

        task = await conn.fetchrow(
            """
            INSERT INTO reaction_tasks
                (channel_id, reaction_type, target_quantity,
                 status, created_by)
            VALUES ($1, $2, $3, 'stopped', $4)
            RETURNING id
            """,
            channel_id,
            reaction_type,
            quantity,
            user_id,
        )

    await log_action(
        actor_id=user_id,
        action="reaction_task_created",
        details={
            "task_id": task["id"],
            "channel_id": channel_id,
            "reaction_type": reaction_type,
            "target_quantity": quantity,
        },
    )

    await update.message.reply_text(
        f"Reaction task record create ho gaya.\n\n"
        f"Task ID: {task['id']}\n"
        f"Channel: {channel['title']}\n"
        f"Reaction: {reaction_type}\n"
        f"Target quantity: {quantity}\n"
        f"Status: stopped\n\n"
        "Note: Actual reactions bhejne wala worker connected nahi hai."
    )


async def list_reaction_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.message:
        return

    allowed, message = await require_permission(
        update.effective_user.id, "manage_reactions"
    )
    if not allowed:
        await update.message.reply_text(message)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                rt.id,
                rt.reaction_type,
                rt.target_quantity,
                rt.status,
                c.title AS channel_title
            FROM reaction_tasks rt
            JOIN channels c ON c.id = rt.channel_id
            ORDER BY rt.id DESC
            LIMIT 30
            """
        )

    if not rows:
        await update.message.reply_text(
            "Abhi koi reaction task record nahi hai."
        )
        return

    lines = ["Reaction task records:\n"]

    for row in rows:
        lines.append(
            f"ID: {row['id']}\n"
            f"Channel: {row['channel_title']}\n"
            f"Reaction: {row['reaction_type']}\n"
            f"Target: {row['target_quantity']}\n"
            f"Status: {row['status']}\n"
        )

    lines.append(
        "Note: Yeh database task records hain; actual reactions "
        "worker connected nahi hai."
    )

    await update.message.reply_text("\n".join(lines))


async def set_reaction_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status: str,
):
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    allowed, message = await require_permission(
        user_id, "manage_reactions"
    )
    if not allowed:
        await update.message.reply_text(message)
        return

    if len(context.args) != 1:
        command = (
            "/startreactions TASK_ID"
            if status == "running"
            else "/stopreactions TASK_ID"
        )
        await update.message.reply_text(
            f"Usage: {command}"
        )
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Task ID number mein honi chahiye."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            """
            SELECT rt.id, rt.channel_id, c.is_active
            FROM reaction_tasks rt
            JOIN channels c ON c.id = rt.channel_id
            WHERE rt.id = $1
            """,
            task_id,
        )

        if not task:
            await update.message.reply_text(
                "Reaction task nahi mila. /reactiontasks check karein."
            )
            return

        if status == "running" and not task["is_active"]:
            await update.message.reply_text(
                "Channel inactive hai. Pehle channel activate karein."
            )
            return

        await conn.execute(
            """
            UPDATE reaction_tasks
            SET status = $1
            WHERE id = $2
            """,
            status,
            task_id,
        )

    await log_action(
        actor_id=user_id,
        action=f"reaction_task_{status}",
        details={"task_id": task_id},
    )

    if status == "running":
        await update.message.reply_text(
            f"Task {task_id} ka status running set ho gaya.\n"
            "Yeh sirf database status hai; actual reactions "
            "automatically nahi bheje jayenge."
        )
    else:
        await update.message.reply_text(
            f"Task {task_id} ka status stopped set ho gaya."
        )


async def start_reactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await set_reaction_status(update, context, "running")


async def stop_reactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await set_reaction_status(update, context, "stopped")


def get_reaction_handlers():
    return [
        CommandHandler("setreaction", set_reaction),
        CommandHandler("reactiontasks", list_reaction_tasks),
        CommandHandler("startreactions", start_reactions),
        CommandHandler("stopreactions", stop_reactions),
    ]
