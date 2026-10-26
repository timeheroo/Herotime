import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS, is_admin
from database import init_db, close_db, register_user, get_user
from groups import init_group_admin_schema, register_group_handlers
register_live_admin_handlers(application)
from live_campaigns import init_live_campaign_schema
from api_accounts import register_api_handlers
from notifications import init_notification_schema
from campaign_reports import register_campaign_report_handlers
from admin_power import init_admin_power_schema, register_admin_power_handlers
from user import register_user_handlers

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

def main_menu(is_owner: bool) -> InlineKeyboardMarkup:
    rows=[[InlineKeyboardButton("👤 My Account",callback_data="my_account"),InlineKeyboardButton("📋 My Tasks",callback_data="my_tasks")],[InlineKeyboardButton("🔗 Invite Links",callback_data="invite_links"),InlineKeyboardButton("💳 My Credits",callback_data="my_credits")],[InlineKeyboardButton("🆘 Contact Admin",callback_data="support")]]
    if is_owner: rows.insert(0,[InlineKeyboardButton("🛡️ Admin Panel",callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def admin_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📂 CHANNELS LIST",callback_data="admin_channels")],[InlineKeyboardButton("🔑 API ACCOUNTS",callback_data="admin_api_list")],[InlineKeyboardButton("🛡️ ALL POWER LIST",callback_data="admin_all_power")],[InlineKeyboardButton("📊 REPORT",callback_data="admin_report")],[InlineKeyboardButton("🏠 MAIN MENU",callback_data="home")]])

def admin_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ADMIN PANEL",callback_data="admin_panel")],[InlineKeyboardButton("🏠 MAIN MENU",callback_data="home")]])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg=update.effective_user; msg=update.effective_message
    if not tg or not msg: return
    owner=is_admin(tg.id)
    try: user=await register_user(telegram_id=tg.id,username=tg.username,display_name=tg.full_name,is_admin=owner)
    except Exception:
        logger.exception('Registration failed'); await msg.reply_text('⚠️ Registration temporarily unavailable.'); return
    if user['status']=='banned': await msg.reply_text('⛔ Your account is disabled.'); return
    if user['status']!='approved': await msg.reply_text('👋 Registration received. Please wait for admin approval.'); return
    await msg.reply_text(f'👋 Welcome, {tg.first_name}! Choose an option:',reply_markup=main_menu(owner))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if not q or not q.from_user: return
    await q.answer(); uid=q.from_user.id; owner=is_admin(uid); action=q.data or ''
    try: user=await get_user(uid)
    except Exception:
        logger.exception('User lookup failed'); await q.edit_message_text('⚠️ Database temporarily unavailable.'); return
    if not user: await q.edit_message_text('Please send /start first.'); return
    if user['status']=='banned': await q.edit_message_text('⛔ Your account is disabled.'); return
    if action=='admin_panel':
        if not owner: await q.edit_message_text('⛔ Main Admin access required.'); return
        await q.edit_message_text('🛡️ ADMIN PANEL',reply_markup=admin_menu()); return
    if action=='home':
        if user['status']!='approved': await q.edit_message_text('⏳ Awaiting admin approval.'); return
        await q.edit_message_text('🏠 MAIN MENU',reply_markup=main_menu(owner)); return
    pages={'admin_channels':'Use /list_groups or /add_group.','admin_api_list':'Use /api_accounts to manage saved API records.','admin_all_power':'Use /Poweradmin to manage Under Admin permissions.','admin_report':'Use /campaign_report for available campaign report.'}
    if action in pages:
        if not owner: await q.edit_message_text('⛔ Main Admin access required.'); return
        await q.edit_message_text(pages[action],reply_markup=admin_back_menu()); return
    if action.startswith('admin_'):
        if not owner: await q.edit_message_text('⛔ Main Admin access required.'); return
        await q.edit_message_text('Feature is not connected yet.',reply_markup=admin_back_menu()); return
    if user['status']!='approved': await q.edit_message_text('⏳ Please wait for admin approval.'); return
    if action=='my_account':
        await q.edit_message_text(
            f"👤 MY ACCOUNT\nName: {user['display_name'] or 'Not set'}\nUsername: @{user['username'] or 'Not set'}\nStatus: {user['status']}\nCredits: {user['credits']}\nSubscription expires: {user['subscription_expires_at'] or 'Not set'}",
            reply_markup=main_menu(owner))
    elif action=='my_credits': await q.edit_message_text(f"💳 Your balance: {user['credits']} credits",reply_markup=main_menu(owner))
    elif action=='my_tasks': await q.edit_message_text('Use /panel to open your task panel.',reply_markup=main_menu(owner))
    elif action=='invite_links': await q.edit_message_text('Use /panel to view available user options.',reply_markup=main_menu(owner))
    elif action=='support': await q.edit_message_text('🆘 Please contact the bot administrator.',reply_markup=main_menu(owner))
    else: await q.edit_message_text('Unknown option.',reply_markup=main_menu(owner))

async def post_init(application: Application):
    logger.info('Initializing PostgreSQL schema')
    await init_db()
    await init_group_admin_schema()
    await init_live_campaign_schema()
    await init_admin_power_schema()
    await init_notification_schema()
    logger.info('Database schemas initialized; configured owner IDs: %s', ADMIN_IDS)

async def post_shutdown(application: Application):
    await close_db()

def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_handler(CommandHandler('start',start_command))
    register_group_handlers(app)
    register_live_admin_handlers(app)  # register quantity/service commands only once
    register_api_handlers(app)
    register_campaign_report_handlers(app)
    register_admin_power_handlers(app)
    register_user_handlers(app)
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info('Starting Telegram Community Manager')
    app.run_polling(allowed_updates=['message','callback_query'],drop_pending_updates=False)

if __name__=='__main__': main()
