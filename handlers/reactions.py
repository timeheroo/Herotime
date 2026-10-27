
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action
from handlers.channels import normalize_channel_input

logger = logging.getLogger(__name__)

ALLOWED_REACTIONS = {
    "like",
    "heart",
    "fire",
    "thumbsup",
    "laugh",
    "sad",
    "wow",
}


async def _authorized(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return False

    allowed, reason = await require_permission(
        user.id,
        "manage_reactions",
    )

    if not allowed:
        await message.reply_text(reason)
        return False

    return True


async def _find_channel(conn, identifier: str):
    username = normalize_channel_input(identifier)

    return await conn.fetchrow(
        """
        SELECT id, title, username, is_active
        FROM channels
        WHERE LOWER(username) = LOWER($1)
        LIMIT 1
        """,
        username,
    )


async def setreaction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message
    user = update.effective_user

    if len(context.args) != 3:
        await message.reply_text(
            "Usage:\n"
            "/setreaction @channel_username REACTION QUANTITY\n\n"
            "Allowed reactions: like, heart, fire, thumbsup, "
            "laugh, sad, wow\n\n"
            "Example:\n"
            "/setreaction @examplechannel heart 20"
        )
        return

    try:
        identifier = context.args[0]
        reaction = context.args[1].lower()
        quantity = int(context.args[2])

        if reaction not in ALLOWED_REACTIONS:
            await message.reply_text(
                "Invalid reaction. Allowed: "
                + ", ".join(sorted(ALLOWED_REACTIONS))
            )
            return

        if quantity < 0:
            raise ValueError("Quantity zero ya usse zyada honi chahiye.")

        pool = await get_pool()

        async with pool.acquire() as conn:
            channel = await _find_channel(conn, identifier)

            if channel is None:
                await message.reply_text(
                    "Channel database mein nahi mila. "
                    "Pehle /addchannel karein."
                )
                return

            if not channel["is_active"]:
                await message.reply_text(
                    "Channel inactive hai. Pehle activate karein."
                )
                return

            row = await conn.fetchrow(
                """
                INSERT INTO reaction_tasks
                    (channel_id, reaction_type, target_quantity,
                     status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, 'stopped', $4, NOW(), NOW())
                RETURNING id
                """,
                channel["id"],
                reaction,
                quantity,
                user.id,
            )

        await log_action(
            user.id,
            "reaction_task_configured",
            {
                "task_id": row["id"],
                "channel": identifier,
                "reaction": reaction,
                "quantity": quantity,
            },
        )

        await message.reply_text(
            "Reaction-task configuration saved.\n"
            f"Task ID: {row['id']}\n"
            f"Channel: {channel['title']}\n"
            f"Reaction type: {reaction}\n"
            f"Target quantity: {quantity}\n"
            "Status: STOPPED"
        )

    except ValueError as exc:
        await message.reply_text(
            f"Invalid input: {exc}\n"
            "Quantity ek non-negative whole number honi chahiye."
        )
    except Exception:
        logger.exception("Failed to configure reaction task")
        await message.reply_text(
            "Reaction-task configuration save nahi ho saki."
        )


async def reactiontasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.reaction_type, t.target_quantity, t.status,
                   c.username, c.title
            FROM reaction_tasks t
            JOIN channels c ON c.id = t.channel_id
            ORDER BY t.id DESC
            LIMIT 50
            """
        )

    if not rows:
        await message.reply_text(
            "Abhi koi reaction task configured nahi hai."
        )
        return

    lines = ["Reaction-task configurations:"]

    for row in rows:
        channel_name = (
            f"@{row['username']}"
            if row["username"]
            else row["title"]
        )

        lines.append(
            f"\nTask ID: {row['id']}"
            f"\nChannel: {channel_name}"
            f"\nReaction: {row['reaction_type']}"
            f"\nTarget: {row['target_quantity']}"
            f"\nStatus: {row['status'].upper()}"
        )

    await message.reply_text("\n".join(lines))


async def _set_reaction_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    active: bool,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message
    user = update.effective_user

    if len(context.args) != 1:
        await message.reply_text(
            "Usage:\n"
            "/startreactions TASK_ID\n"
            "/stopreactions TASK_ID"
        )
        return

    try:
        task_id = int(context.args[0])
        if task_id <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("Task ID positive number hona chahiye.")
        return

    new_status = "running" if active else "stopped"
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE reaction_tasks AS t
            SET status = $1, updated_at = NOW()
            FROM channels AS c
            WHERE t.id = $2
              AND c.id = t.channel_id
              AND ($3 = FALSE OR c.is_active = TRUE)
            RETURNING t.id, t.reaction_type, t.target_quantity,
                      c.title, c.username
            """,
            new_status,
            task_id,
            active,
        )

    if row is None:
        await message.reply_text(
            "Task nahi mila, ya channel inactive hai."
        )
        return

    await log_action(
        user.id,
        "reaction_task_started" if active else "reaction_task_stopped",
        {"task_id": task_id},
    )

    channel_name = (
        f"@{row['username']}"
        if row["username"]
        else row["title"]
    )

    await message.reply_text(
        f"Task ID: {task_id}\n"
        f"Channel: {channel_name}\n"
        f"Reaction: {row['reaction_type']}\n"
        f"Target: {row['target_quantity']}\n"
        f"Database status: {new_status.upper()}\n\n"
        "Note: Status save hua hai. Ye code actual reactions "
        "automatically send nahi karta."
    )


async def startreactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_reaction_status(update, context, True)


async def stopreactions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_reaction_status(update, context, False)


def get_reaction_handlers():
    return [
        CommandHandler("setreaction", setreaction),
        CommandHandler("reactiontasks", reactiontasks),
        CommandHandler("startreactions", startreactions),
        CommandHandler("stopreactions", stopreactions),
    ]
