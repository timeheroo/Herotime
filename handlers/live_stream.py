
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action
from handlers.channels import normalize_channel_input

logger = logging.getLogger(__name__)


async def _authorized(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return False

    allowed, reason = await require_permission(
        user.id,
        "manage_live",
    )

    if not allowed:
        await message.reply_text(reason)
        return False

    return True


async def _find_channel(conn, identifier: str):
    username = normalize_channel_input(identifier)

    return await conn.fetchrow(
        """
        SELECT id, telegram_id, username, title, is_active
        FROM channels
        WHERE LOWER(username) = LOWER($1)
        LIMIT 1
        """,
        username,
    )


async def setlivetarget(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message
    user = update.effective_user

    if len(context.args) != 2:
        await message.reply_text(
            "Usage:\n"
            "/setlivetarget @channel_username QUANTITY\n"
            "Example:\n"
            "/setlivetarget @examplechannel 10"
        )
        return

    try:
        identifier = context.args[0]
        quantity = int(context.args[1])

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
                    "Ye channel inactive hai. Pehle activate karein."
                )
                return

            row = await conn.fetchrow(
                """
                INSERT INTO live_tasks
                    (channel_id, target_quantity, status, created_by,
                     created_at, updated_at)
                VALUES ($1, $2, 'stopped', $3, NOW(), NOW())
                RETURNING id
                """,
                channel["id"],
                quantity,
                user.id,
            )

        await log_action(
            user.id,
            "live_target_configured",
            {
                "task_id": row["id"],
                "channel": identifier,
                "quantity": quantity,
            },
        )

        await message.reply_text(
            "Live-task configuration saved.\n"
            f"Task ID: {row['id']}\n"
            f"Channel: {channel['title']}\n"
            f"Target quantity: {quantity}\n"
            "Status: STOPPED"
        )

    except ValueError as exc:
        await message.reply_text(
            f"Invalid input: {exc}\n"
            "Quantity ek non-negative whole number honi chahiye."
        )
    except Exception:
        logger.exception("Failed to configure live task")
        await message.reply_text(
            "Live-task configuration save nahi ho saki."
        )


async def livetasks(
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
            SELECT t.id, t.target_quantity, t.status,
                   c.username, c.title
            FROM live_tasks t
            JOIN channels c ON c.id = t.channel_id
            ORDER BY t.id DESC
            LIMIT 50
            """
        )

    if not rows:
        await message.reply_text("Abhi koi live task configured nahi hai.")
        return

    lines = ["Live-task configurations:"]

    for row in rows:
        channel_name = (
            f"@{row['username']}"
            if row["username"]
            else row["title"]
        )
        lines.append(
            f"\nTask ID: {row['id']}"
            f"\nChannel: {channel_name}"
            f"\nTarget: {row['target_quantity']}"
            f"\nStatus: {row['status'].upper()}"
        )

    await message.reply_text("\n".join(lines))


async def _set_live_status(
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
            "/startlive TASK_ID\n"
            "/stoplive TASK_ID"
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
            UPDATE live_tasks AS t
            SET status = $1, updated_at = NOW()
            FROM channels AS c
            WHERE t.id = $2
              AND c.id = t.channel_id
              AND ($3 = FALSE OR c.is_active = TRUE)
            RETURNING t.id, t.target_quantity, c.title, c.username
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
        "live_task_started" if active else "live_task_stopped",
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
        f"Target: {row['target_quantity']}\n"
        f"Database status: {new_status.upper()}\n\n"
        "Note: Status change save hua hai; actual live-stream worker "
        "is code mein included nahi hai."
    )


async def startlive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_live_status(update, context, True)


async def stoplive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_live_status(update, context, False)


def get_live_handlers():
    return [
        CommandHandler("setlivetarget", setlivetarget),
        CommandHandler("livetasks", livetasks),
        CommandHandler("startlive", startlive),
        CommandHandler("stoplive", stoplive),
      ]
