```python
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import has_permission
from utils.logger import log_action
from utils.validators import validate_reaction_type

logger = logging.getLogger(__name__)


async def set_reaction_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_reactions"):
        await message.reply_text(
            "❌ Aapko reaction-task manage karne ki permission nahi hai."
        )
        return

    if len(context.args) != 3:
        await message.reply_text(
            "Use:\n/setreaction CHANNEL_ID REACTION QUANTITY\n\n"
            "Example:\n/setreaction 1 heart 10"
        )
        return

    try:
        channel_id = int(context.args[0])
        quantity = int(context.args[2])

        if channel_id <= 0 or quantity <= 0:
            raise ValueError

        reaction = validate_reaction_type(context.args[1])

    except ValueError as exc:
        await message.reply_text(
            f"❌ Invalid input: {exc}\n"
            "Reaction: like, heart, fire, thumbsup, laugh, sad, wow"
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
                INSERT INTO reaction_tasks
                    (channel_id, reaction_type, target_quantity, status)
                VALUES ($1, $2, $3, 'stopped')
                RETURNING id
                """,
                channel_id,
                reaction,
                quantity,
            )

        await log_action(
            user.id,
            "create_reaction_task",
            {
                "task_id": task["id"],
                "channel_id": channel_id,
                "reaction": reaction,
                "quantity": quantity,
            },
        )

        await message.reply_text(
            "✅ Reaction-task configuration create ho gayi.\n"
            f"Task ID: {task['id']}\n"
            f"Channel: {channel['title']}\n"
            f"Reaction: {reaction}\n"
            f"Target quantity: {quantity}\n"
            "Status: stopped"
        )

    except Exception:
        logger.exception("Failed to create reaction task")
        await message.reply_text(
            "❌ Task create nahi hua. Database schema aur Railway logs che
```
