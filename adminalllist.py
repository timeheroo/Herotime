
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import is_admin


COMMAND_SECTIONS = [
    (
        "🛡️ GENERAL ADMIN",
        [
            ("/admin", "Admin panel"),
            ("/adminalllist", "Admin command directory"),
            ("/admin_help", "Command help"),
            ("/admin_stats", "User statistics"),
            ("/audit_logs", "Admin activity logs"),
        ],
    ),
    (
        "👥 USER MANAGEMENT",
        [
            ("/pending_users", "Pending users list"),
            ("/approved_users", "Approved users list"),
            ("/approve_user TELEGRAM_ID", "Approve a user"),
            ("/ban_user TELEGRAM_ID", "Ban a user"),
            ("/unban_user TELEGRAM_ID", "Unban a user"),
            ("/user_info TELEGRAM_ID", "User details"),
        ],
    ),
    (
        "💳 CREDITS",
        [
            ("/add_credit TELEGRAM_ID AMOUNT REASON", "Add credits"),
            ("/deduct_credit TELEGRAM_ID AMOUNT REASON", "Deduct credits"),
            ("/credit_balance TELEGRAM_ID", "Check balance"),
            ("/credit_history TELEGRAM_ID", "Transaction history"),
        ],
    ),
    (
        "📢 GROUPS AND CHANNELS",
        [
            ("/add_group @USERNAME source", "Register a source group"),
            ("/add_group @USERNAME target", "Register a target group"),
            ("/groups", "List registered groups"),
            ("/all_channels", "List registered channels"),
            ("/list_groups", "Alternative group list command"),
            ("/search_group KEYWORD", "Search groups"),
            ("/group_info GROUP_ID", "Group details"),
            ("/update_invite GROUP_ID URL", "Update invite link"),
            ("/remove_group GROUP_ID", "Remove a group"),
            ("/pause_group GROUP_ID", "Pause group service"),
            ("/resume_group GROUP_ID", "Resume group service"),
        ],
    ),
    (
        "⚙️ QUANTITY AND SERVICE",
        [
            ("/set_quantity GROUP_ID QUANTITY", "Set target quantity"),
            ("/increase_quantity GROUP_ID AMOUNT", "Increase quantity"),
            ("/decrease_quantity GROUP_ID AMOUNT", "Decrease quantity"),
            ("/start_service GROUP_ID", "Enable service"),
            ("/stop_service GROUP_ID", "Disable service"),
            ("/live_status GROUP_ID", "Show saved service settings"),
            ("/all_services", "List service settings"),
            ("/campaign_report", "Report for all groups"),
            ("/campaign_report GROUP_ID", "Report for one group"),
        ],
    ),
    (
        "🔑 API ACCOUNT MANAGEMENT",
        [
            ("/add_api NAME API_ID API_HASH", "Save API account details"),
            ("/api_accounts", "List saved API accounts"),
            ("/remove_api NAME", "Remove saved API account details"),
        ],
    ),
    (
        "ℹ️ IMPORTANT NOTES",
        [
            (
                "GROUP_ID",
                "Use the internal database group ID, not the Telegram -100 chat ID.",
            ),
            (
                "TARGET GROUP",
                "Quantity commands require a group registered with type target.",
            ),
            (
                "SERVICE STATUS",
                "Starting service updates saved settings; it does not itself guarantee campaign execution.",
            ),
            (
                "REPORTS",
                "Reports show stored settings and recorded events, not actual viewers or spend.",
            ),
            (
                "API SECURITY",
                "Never share API hashes, bot tokens, passwords, OTPs, or session secrets in chat.",
            ),
        ],
    ),
]


def _format_command_list() -> str:
    parts = [
        "🛡️ ADMIN CONTROL PANEL — COMMAND DIRECTORY",
        "",
        "Commands are listed by module. A command works only when its "
        "handler is registered and its dependencies are configured.",
        "",
    ]

    for section, commands in COMMAND_SECTIONS:
        parts.append(section)

        for command, description in commands:
            parts.append(f"{command} — {description}")

        parts.append("")

    return "\n".join(parts)


async def adminalllist_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if not is_admin(user.id):
        await message.reply_text(
            "⛔ Access denied. Yeh command sirf admin ke liye hai."
        )
        return

    output = _format_command_list()
    chunks = []
    current = ""

    for line in output.splitlines():
        candidate = f"{current}\n{line}" if current else line

        if len(candidate) > 3500:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    total = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        header = f"📄 Part {index}/{total}\n\n" if total > 1 else ""
        await message.reply_text(header + chunk)


async def admin_help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await adminalllist_command(update, context)


def register_adminalllist_handlers(
    application: Application,
) -> None:
    application.add_handler(
        CommandHandler("adminalllist", adminalllist_command)
    )
    application.add_handler(
        CommandHandler("admin_help", admin_help_command)
    )
