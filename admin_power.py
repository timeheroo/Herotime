# admin_power.py — Main Admin and per-command Under Admin permissions
# Safe additive schema only; does not delete/reset existing project data.
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
import config
import database

logger = logging.getLogger(__name__)
COMMANDS = {
    "General": ["admin", "addnewadmin", "removeadmin", "poweradmin", "adminalllist", "admin_help", "admin_stats", "bot_status"],
    "Groups": ["add_group", "remove_group", "list_groups", "search_group", "group_info", "pause_group", "resume_group"],
    "Quantity/service": ["set_quantity", "increase_quantity", "decrease_quantity", "start_service", "stop_service", "live_status", "all_services"],
    "API/accounts": ["api_accounts", "add_api", "api_info", "rename_account", "update_api", "remove_api", "rename_profile", "account_status", "disconnect_account"],
    "Reports": ["daily_report", "weekly_report", "monthly_report", "last24h", "last72", "channel_report", "quantity_report", "campaign_report"],
}
ALL_COMMANDS = {c.lower() for values in COMMANDS.values() for c in values}

async def init_admin_power_schema():
    async with database.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_command_permissions (
                admin_telegram_id BIGINT NOT NULL,
                command_name TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                updated_by BIGINT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (admin_telegram_id, command_name)
            )
        """)

async def has_command_permission(telegram_id: int, command: str) -> bool:
    if config.is_admin(telegram_id):
        return True
    key = command.strip().lstrip('/').lower()
    if key not in ALL_COMMANDS:
        return False
    async with database.connection() as conn:
        enabled = await conn.fetchval(
            "SELECT enabled FROM admin_command_permissions WHERE admin_telegram_id=$1 AND LOWER(command_name)=$2",
            telegram_id, key)
    return bool(enabled)

async def _deny(update: Update):
    msg = update.effective_message
    if msg:
        await msg.reply_text("⛔ Sirf Main Admin ye action kar sakta hai.")

async def _directory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; msg=update.effective_message
    if not u or not msg: return
    if not config.is_admin(u.id): return await _deny(update)
    rows=[]
    for category, cmds in COMMANDS.items():
        rows.append([InlineKeyboardButton(f"📂 {category}", callback_data=f"power:cat:{list(COMMANDS).index(category)}")])
    rows.append([InlineKeyboardButton("👥 Under Admin list", callback_data="power:admins")])
    await msg.reply_text("🛡️ ADMIN COMMAND DIRECTORY\nChoose category or Under Admin:", reply_markup=InlineKeyboardMarkup(rows))

async def _show_admins(q):
    async with database.connection() as conn:
        rows=await conn.fetch("SELECT telegram_id, display_name, username FROM users WHERE LOWER(COALESCE(role,'')) IN ('admin','under_admin') AND status='approved' ORDER BY display_name NULLS LAST LIMIT 100")
    rows=[r for r in rows if int(r['telegram_id']) not in config.ADMIN_IDS]
    buttons=[[InlineKeyboardButton(f"{r['display_name'] or r['username'] or 'Admin'} · {r['telegram_id']}", callback_data=f"power:user:{r['telegram_id']}:0")] for r in rows]
    buttons.append([InlineKeyboardButton("📚 Directory", callback_data="power:directory")])
    await q.edit_message_text("👥 UNDER ADMIN LIST\nSelect an admin to manage permissions." if rows else "No approved Under Admin found. Use /addnewadmin TELEGRAM_ID after they send /start.", reply_markup=InlineKeyboardMarkup(buttons))

async def _show_user(q, target_id, cat_index=0):
    cats=list(COMMANDS); cat_index=max(0,min(cat_index,len(cats)-1)); category=cats[cat_index]
    async with database.connection() as conn:
        rows=await conn.fetch("SELECT command_name,enabled FROM admin_command_permissions WHERE admin_telegram_id=$1", target_id)
    saved={r['command_name'].lower():r['enabled'] for r in rows}
    buttons=[]
    for cmd in COMMANDS[category]:
        on=saved.get(cmd.lower(),False)
        buttons.append([InlineKeyboardButton(f"{'🟢 ON' if on else '🔴 OFF'} /{cmd}", callback_data=f"power:toggle:{target_id}:{cmd.lower()}:{cat_index}")])
    nav=[]
    if cat_index: nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"power:user:{target_id}:{cat_index-1}"))
    if cat_index<len(cats)-1: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"power:user:{target_id}:{cat_index+1}"))
    if nav: buttons.append(nav)
    buttons += [[InlineKeyboardButton("👥 Under Admin list", callback_data="power:admins")],[InlineKeyboardButton("📚 Directory", callback_data="power:directory")]]
    await q.edit_message_text(f"🛡️ UNDER ADMIN PERMISSIONS\nID: {target_id}\nCategory: {category}\nDefault: OFF. Tap a command to toggle.", reply_markup=InlineKeyboardMarkup(buttons))

async def _callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if not q: return
    actor=q.from_user.id
    if not config.is_admin(actor):
        await q.answer("Only Main Admin can manage permissions.", show_alert=True); return
    await q.answer()
    p=(q.data or '').split(':')
    try:
        if p[1]=='directory':
            buttons=[[InlineKeyboardButton(f"📂 {c}", callback_data=f"power:cat:{i}")] for i,c in enumerate(COMMANDS)]
            buttons.append([InlineKeyboardButton("👥 Under Admin list", callback_data="power:admins")])
            await q.edit_message_text("🛡️ ADMIN COMMAND DIRECTORY", reply_markup=InlineKeyboardMarkup(buttons))
        elif p[1]=='admins': await _show_admins(q)
        elif p[1]=='cat':
            i=int(p[2]); cat=list(COMMANDS)[i]
            await q.edit_message_text("📂 "+cat+"\n\n"+"\n".join('/'+c for c in COMMANDS[cat]), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 Under Admin list",callback_data="power:admins")],[InlineKeyboardButton("📚 Directory",callback_data="power:directory")]]))
        elif p[1]=='user': await _show_user(q,int(p[2]),int(p[3]))
        elif p[1]=='toggle':
            target=int(p[2]); cmd=p[3].lower(); idx=int(p[4])
            if cmd not in ALL_COMMANDS or target in config.ADMIN_IDS: raise ValueError('Invalid target/command')
            async with database.connection() as conn:
                role=await conn.fetchval("SELECT role FROM users WHERE telegram_id=$1",target)
                if role not in ('admin','under_admin'): raise ValueError('Target is not an Under Admin')
                current=await conn.fetchval("SELECT enabled FROM admin_command_permissions WHERE admin_telegram_id=$1 AND LOWER(command_name)=$2",target,cmd)
                await conn.execute("""INSERT INTO admin_command_permissions(admin_telegram_id,command_name,enabled,updated_by,updated_at) VALUES($1,$2,$3,$4,NOW()) ON CONFLICT(admin_telegram_id,command_name) DO UPDATE SET enabled=EXCLUDED.enabled,updated_by=EXCLUDED.updated_by,updated_at=NOW()""",target,cmd,not bool(current),actor)
            await _show_user(q,target,idx)
    except Exception:
        logger.exception('Admin power callback failed')
        await q.edit_message_text("❌ Panel error. Railway logs check karein.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Directory",callback_data="power:directory")]]))

async def _add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; m=update.effective_message
    if not u or not m: return
    if not config.is_admin(u.id): return await _deny(update)
    if not context.args:
        await m.reply_text("Usage: /addnewadmin TELEGRAM_ID (user must first send /start)"); return
    try: target=int(context.args[0]); assert target>0
    except Exception:
        await m.reply_text("❌ Valid numeric Telegram ID dein."); return
    if target in config.ADMIN_IDS:
        await m.reply_text("Ye ID already Main Admin hai."); return
    async with database.connection() as conn:
        row=await conn.fetchrow("SELECT status FROM users WHERE telegram_id=$1",target)
        if not row:
            await m.reply_text("User nahi mila. Pehle us user se bot par /start karwayein."); return
        if row['status']=='banned':
            await m.reply_text("Banned user ko admin nahi bana sakte."); return
        await conn.execute("UPDATE users SET role='admin',status='approved' WHERE telegram_id=$1",target)
    await m.reply_text(f"✅ Under Admin add ho gaya: {target}. Commands default OFF hain; /Poweradmin se permissions set karein.")

async def _remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; m=update.effective_message
    if not u or not m: return
    if not config.is_admin(u.id): return await _deny(update)
    if not context.args:
        await m.reply_text("Usage: /Removeadmin TELEGRAM_ID"); return
    try: target=int(context.args[0]); assert target>0
    except Exception:
        await m.reply_text("❌ Valid numeric Telegram ID dein."); return
    if target in config.ADMIN_IDS:
        await m.reply_text("⛔ Main Admin ko remove nahi kar sakte."); return
    async with database.connection() as conn:
        async with conn.transaction():
            role=await conn.fetchval("SELECT role FROM users WHERE telegram_id=$1",target)
            if role not in ('admin','under_admin'):
                await m.reply_text("Under Admin nahi mila."); return
            await conn.execute("UPDATE users SET role='user' WHERE telegram_id=$1",target)
            await conn.execute("DELETE FROM admin_command_permissions WHERE admin_telegram_id=$1",target)
    await m.reply_text(f"✅ Under Admin access removed for {target}. User account/data delete nahi hua.")

async def _admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; m=update.effective_message
    if not u or not m: return
    if not config.is_admin(u.id): return await _deny(update)
    await m.reply_text("Admin commands:\n/adminalllist — command directory and permissions\n/addnewadmin TELEGRAM_ID\n/Removeadmin TELEGRAM_ID\n/Poweradmin — permission panel\n\nNote: permission toggles only affect commands whose handlers call has_command_permission().")

def register_admin_power_handlers(application: Application):
    application.add_handler(CommandHandler("adminalllist", _directory))
    application.add_handler(CommandHandler("poweradmin", _directory))
    application.add_handler(CommandHandler("admin", _directory))
    application.add_handler(CommandHandler("admin_help", _admin_help))
    application.add_handler(CommandHandler("addnewadmin", _add_admin))
    application.add_handler(CommandHandler("removeadmin", _remove_admin))
    application.add_handler(CallbackQueryHandler(_callback, pattern=r"^power:"))
