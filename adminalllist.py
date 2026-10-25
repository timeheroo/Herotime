"""
Admin command directory for Telegram Community Manager Bot.

This file implements /adminalllist and /admin_help only.
It documents the planned command set; commands listed here are NOT automatically
implemented by this file. Their handlers must be implemented and registered in
their respective modules.

Compatible with python-telegram-bot v21+.
"""

from telegram import Update
from telegram.ext import ContextTypes

try:
    from config import is_admin
except ImportError:
    def is_admin(user_id: int) -> bool:
        # Safe default: deny access if config.is_admin is unavailable.
        return False


COMMAND_SECTIONS = [
    (
        "👑 GENERAL ADMIN",
        [
            ("/admin", "Admin panel open kare"),
            ("/adminalllist", "Saari admin commands aur unka kaam dikhaye"),
            ("/admin_help", "Admin command help dikhaye"),
            ("/admin_stats", "Bot ke overall statistics dikhaye"),
            ("/bot_status", "Bot status check kare"),
        ],
    ),
    (
        "👥 USER MANAGEMENT",
        [
            ("/pending_users", "Approval ka intezar kar rahe users dikhaye"),
            ("/approved_users", "Approved users ki list dikhaye"),
            ("/approve_user USER_ID", "User ko approve kare"),
            ("/ban_user USER_ID", "User ko ban kare"),
            ("/unban_user USER_ID", "User ka ban hataye"),
            ("/user_info USER_ID", "User ki details dikhaye"),
        ],
    ),
    (
        "📢 CHANNEL / GROUP MANAGEMENT",
        [
            ("/add_group", "Naya channel/group add karne ka flow"),
            ("/list_groups", "Saved channels/groups ki list"),
            ("/search_group @username", "Username se channel/group search kare"),
            ("/group_info @username", "Saved channel/group details dikhaye"),
            ("/update_invite @username LINK", "Saved invite link update kare"),
            ("/remove_group @username", "Saved channel/group entry remove kare"),
            ("/pause_group @username", "Us group ki service pause kare"),
            ("/resume_group @username", "Us group ki service resume kare"),
        ],
    ),
    (
        "⚙️ SERVICE & QUANTITY",
        [
            ("/set_quantity @username NUMBER", "Configured target quantity set kare"),
            ("/increase_quantity @username NUMBER", "Configured quantity badhaye"),
            ("/decrease_quantity @username NUMBER", "Configured quantity ghataye"),
            ("/start_service @username", "Service enable kare"),
            ("/stop_service @username", "Service disable kare"),
            ("/live_status @username", "Saved service/stream status dikhaye"),
            ("/all_services", "Sabhi saved services ka status dikhaye"),
            ("/campaign_report", "Campaign settings aur available records dikhaye"),
        ],
    ),
    (
        "🔑 API & ACCOUNT MANAGEMENT",
        [
            ("/api_accounts", "Saved API account entries dikhaye"),
            ("/add_api", "API ID/API Hash entry add karne ka flow"),
            ("/api_info ACCOUNT_NAME", "Account entry ki non-secret details dikhaye"),
            ("/rename_account OLD_NAME NEW_NAME", "Bot ke andar custom account label badle"),
            ("/update_api ACCOUNT_NAME", "Saved API credentials update kare"),
            ("/remove_api ACCOUNT_NAME", "Saved API entry remove kare"),
            ("/connect_account ACCOUNT_NAME", "Authorized account authentication flow"),
            ("/disconnect_account ACCOUNT_NAME", "Account session disconnect/revoke flow"),
            ("/account_status ACCOUNT_NAME", "Account connection status dikhaye"),
            ("/rename_profile ACCOUNT_NAME", "Authorized Telegram profile-name update flow"),
        ],
    ),
    (
        "💳 CREDITS",
        [
            ("/add_credit USER_ID AMOUNT", "User credits add kare"),
            ("/deduct_credit USER_ID AMOUNT", "User credits deduct kare"),
            ("/credit_balance USER_ID", "User ka current balance dikhaye"),
            ("/credit_history USER_ID", "User ki transaction history dikhaye"),
        ],
    ),
    (
        "📊 REPORTS",
        [
            ("/daily_report", "Aaj ka report"),
            ("/weekly_report", "Pichhle 7 din ka report"),
            ("/monthly_report", "Is mahine ka report"),
            ("/last24h", "Pichhle 24 ghante ka report"),
            ("/last72h", "Pichhle 72 ghante ka report"),
            ("/channel_report @username", "Ek channel ka report"),
            ("/stream_duration @username", "Available records se stream duration"),
            ("/quantity_report @username", "Configured quantity aur available count"),
            ("/spend_report", "Recorded spending report"),
            ("/export_report", "Report export flow, agar implement ho"),
        ],
    ),
    (
        "📋 TASKS, NOTIFICATIONS & SECURITY",
        [
            ("/tasks", "Task list"),
            ("/task_info TASK_ID", "Task details"),
            ("/pause_task TASK_ID", "Task pause kare"),
            ("/resume_task TASK_ID", "Task resume kare"),
            ("/cancel_task TASK_ID", "Task cancel kare"),
            ("/announce", "Announcement bhejne ka flow"),
            ("/audit_logs", "Admin activity history"),
            ("/database_status", "Database connection status"),
        ],
    ),
]


def _format_command_list() -> str:
    parts = [
        "🛡️ ADMIN CONTROL PANEL — COMMAND DIRECTORY",
        "",
        "Yeh command directory hai. Kisi command ka listed hona yeh guarantee nahi "
        "karta ki uska handler abhi project mein implemented hai.",
        "",
    ]
    for section, commands in COMMAND_SECTIONS:
        parts.append(section)
        for command, description in commands:
            parts.append(f"{command} — {description}")
        parts.append("")
    parts.extend([
        "⚠️ IMPORTANT",
        "• Quantity setting configured target hai; actual viewer count ki guarantee nahi.",
        "• Actual viewers/stream duration sirf reliable data source milne par report honge.",
        "• API ID/API Hash se akela account login nahi hota; authorized authentication/session chahiye.",
        "• API Hash, OTP, password ya session secrets ko chat/logs mein share na karein.",
    ])
    return "\n".join(parts)


async def adminalllist_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return
    if not is_admin(user.id):
        await message.reply_text("⛔ Access denied. Yeh command sirf admin ke liye hai.")
        return

    text = _format_command_list()
    # Telegram message limit is 4096 characters. Split at line boundaries.
    chunks = []
    current = ""
    for line in text.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > 3800:
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
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await adminalllist_command(update, context)
