
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action


async def add_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
        {"account_id": account_id, "label": label},
    )

    await message.reply_text(
        "✅ Account record created.\n\n"
        f"Record ID: {account_id}\n"
        f"Label: {label}\n"
        "Status: pending\n\n"
        "Important: Yeh database record hai. Isse Telegram account "
        "login, join ya authorize nahi hua hai."
    )


async def list_accounts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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

    lines = ["📱 Account Records — Latest 50"]

    for account in accounts:
        created = account["created_at"].strftime(
            "%Y-%m-%d %H:%M UTC"
        )
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
        row = await conn.fetchrow(
            """
            UPDATE accounts
            SET status = 'inactive'
            WHERE id = $1 AND status <> 'inactive'
            RETURNING id, label
            """,
            account_id,
        )

    if row is None:
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
        "✅ Account record inactive mark kar diya.\n"
        f"Record ID: {row['id']}\n"
        f"Label: {row['label']}\n\n"
        "Note: Isse database record inactive hua hai; kisi "
        "Telegram session ko disconnect nahi kiya gaya."
    )


def get_account_handlers():
    return [
        CommandHandler("addaccount", add_account),
        CommandHandler("accounts", list_accounts),
        CommandHandler("deactivateaccount", deactivate_account),
    ]
