
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action


async def add_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Register an account record without collecting login secrets."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_accounts"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    label = " ".join(context.args).strip()

    if not label:
        await message.reply_text(
            "Usage: /addaccount ACCOUNT_LABEL\n"
            "Example: /addaccount My authorized account"
        )
        return

    if len(label) > 80:
        await message.reply_text(
            "Account label 80 characters se chhota rakhein."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        account_id = await conn.fetchval(
            """
            INSERT INTO accounts (label, status, created_by)
            VALUES ($1, 'pending', $2)
            RETURNING id
            """,
            label,
            user.id,
        )

    await log_action(
        user.id,
        "account_record_added",
        {
            "account_id": account_id,
            "label": label,
        },
    )

    await message.reply_text(
        f"✅ Account record created.\n"
        f"Record ID: {account_id}\n"
        f"Label: {label}\n"
        "Status: pending\n\n"
        "Note: Yeh sirf database record hai. "
        "Isse Telegram account login ya authorize nahi hua hai."
    )


async def list_accounts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """List registered account records without showing session data."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_accounts"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        accounts = await conn.fetch(
            """
            SELECT id, label, status, created_at
            FROM accounts
            ORDER BY id DESC
            LIMIT 50
            """
        )

    if not accounts:
        await message.reply_text(
            "Abhi koi account record nahi hai."
        )
        return

    lines = ["📱 Account Records"]

    for account in accounts:
        created = account["created_at"].strftime("%Y-%m-%d %H:%M UTC")

        lines.append(
            f"\nRecord ID: {account['id']}\n"
            f"Label: {account['label']}\n"
            f"Status: {account['status']}\n"
            f"Created: {created}"
        )

    await message.reply_text("\n".join(lines))


async def deactivate_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Mark an account record inactive."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_accounts"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await message.reply_text(
            "Usage: /deactivateaccount ACCOUNT_ID"
        )
        return

    account_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE accounts
            SET status = 'inactive'
            WHERE id = $1 AND status <> 'inactive'
            """,
            account_id,
        )

    if result.endswith("0"):
        await message.reply_text(
            "Account record nahi mila, ya pehle se inactive hai."
        )
        return

    await log_action(
        user.id,
        "account_deactivated",
        {"account_id": account_id},
    )

    await message.reply_text(
        f"✅ Account record {account_id} inactive mark kar diya."
    )


def get_account_handlers():
    """Return account-management command handlers."""
    return [
        CommandHandler("addaccount", add_account),
        CommandHandler("accounts", list_accounts),
        CommandHandler("deactivateaccount", deactivate_account),
    ]
