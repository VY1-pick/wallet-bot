import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# شناسه مدیر اصلی
ADMIN_PIN = "123456"

# ایجاد دیتابیس و جدول برای کاربران، رسیدها، تنظیمات و مدیر اصلی
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    # ایجاد جدول کاربران
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            transactions TEXT DEFAULT ''
        )
    """)
    # ایجاد جدول رسیدها
    c.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER,
            image_url TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    # ایجاد جدول ادمین‌ها
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY,
            user_id INTEGER
        )
    """)
    # ایجاد جدول تنظیمات
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            setting_id INTEGER PRIMARY KEY,
            key TEXT,
            value TEXT
        )
    """)
    # ایجاد جدول مدیر اصلی
    c.execute("""
        CREATE TABLE IF NOT EXISTS main_admin (
            id INTEGER PRIMARY KEY,
            username TEXT,
            user_id INTEGER
        )
    """)
    # ایجاد جدول تنظیمات عضویت اجباری
    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_settings (
            id INTEGER PRIMARY KEY,
            channel_id TEXT,
            is_mandatory INTEGER DEFAULT 0
        )
    """)
    # تنظیمات پیش‌فرض
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('robot_status', 'active')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_number', '5022291530689296')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate', '1000')")
    c.execute("INSERT OR IGNORE INTO channel_settings (channel_id, is_mandatory) VALUES ('', 0)")  # کانال خالی و عضویت غیرفعال
    conn.commit()
    conn.close()

# ثبت‌نام کاربر جدید
def register_user(user_id, username):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

# دریافت موجودی کاربر
def get_balance(user_id):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = c.fetchone()
    conn.close()
    return balance[0] if balance else 0

# چک کردن اینکه آیا مدیر اصلی تنظیم شده است یا نه
def check_main_admin():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("SELECT * FROM main_admin")
    admin = c.fetchone()
    conn.close()
    return admin

# چک کردن عضویت در کانال
async def check_channel_membership(update: Update, context: CallbackContext):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'channel_id'")
    channel_id = c.fetchone()[0]
    c.execute("SELECT value FROM channel_settings WHERE id = 1")
    is_mandatory = c.fetchone()[0]
    conn.close()

    if is_mandatory:
        # اگر عضویت اجباری باشد
        user_id = update.message.from_user.id
        member_status = await context.bot.get_chat_member(channel_id, user_id)
        
        if member_status.status not in ['member', 'administrator']:
            await update.message.reply_text("برای استفاده از ربات باید ابتدا در کانال عضو شوید.")
            return False
    return True

# شروع ربات و منو
async def start(update: Update, context: CallbackContext) -> None:
    if not check_main_admin():
        reply_markup = ForceReply(selective=True)
        await update.message.reply_text(
            "مدیر اصلی مشخص نشده است. لطفاً کد امنیتی را وارد کنید.",
            reply_markup=reply_markup
        )
        return

    if not await check_channel_membership(update, context):
        return  # اگر کاربر در کانال نیست، اجازه ادامه نخواهد داشت

    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # ثبت‌نام کاربر
    register_user(user_id, username)

    # ایجاد منوی اصلی با دکمه‌ها
    keyboard = [
        ["افزایش موجودی", "مشاهده موجودی"],
        ["پروفایل", "راهنما"],
        ["تنظیمات"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    # ارسال پیام خوشامد
    await update.message.reply_text(
        f"سلام {username}! خوش آمدید به ربات کیف پول PXT. برای شروع یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=reply_markup
    )

# مشخص کردن مدیر اصلی
async def set_main_admin(update: Update, context: CallbackContext) -> None:
    entered_code = update.message.text.strip().lower()
    
    if entered_code == ADMIN_PIN:
        user_id = update.message.from_user.id
        username = update.message.from_user.username
        
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute("INSERT INTO main_admin (username, user_id) VALUES (?, ?)", (username, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text("مدیر اصلی با موفقیت ثبت شد!")
    else:
        await update.message.reply_text("کد امنیتی اشتباه است. لطفاً دوباره تلاش کنید.")

# منو تنظیمات
async def settings(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("فعال/غیرفعال کردن عضویت اجباری", callback_data='toggle_membership')],
        [InlineKeyboardButton("تغییر کانال", callback_data='change_channel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مدیر عزیز، لطفاً یکی از گزینه‌ها را انتخاب کنید.", reply_markup=reply_markup)

# تغییر وضعیت عضویت اجباری
async def toggle_membership(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("SELECT is_mandatory FROM channel_settings WHERE id = 1")
    current_status = c.fetchone()[0]
    new_status = 1 if current_status == 0 else 0
    c.execute("UPDATE channel_settings SET is_mandatory = ? WHERE id = 1", (new_status,))
    conn.commit()
    conn.close()

    status_text = "عضویت اجباری فعال شد." if new_status == 1 else "عضویت اجباری غیرفعال شد."
    await update.message.reply_text(status_text)

# تغییر شناسه کانال
async def change_channel(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("لطفاً شناسه کانال جدید را وارد کنید:")

# دریافت شناسه کانال جدید
async def set_new_channel(update: Update, context: CallbackContext) -> None:
    new_channel_id = update.message.text.strip()

    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("UPDATE channel_settings SET channel_id = ? WHERE id = 1", (new_channel_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"شناسه کانال به {new_channel_id} تغییر یافت.")

# مدیریت CallbackQuery برای دکمه‌ها
async def handle_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # پاسخ به callback query
    callback_data = query.data

    if callback_data == 'toggle_membership':
        await toggle_membership(update, context)
    elif callback_data == 'change_channel':
        await change_channel(update, context)

# تابع اصلی
def main():
    create_db()  # ساخت دیتابیس

    # ایجاد Application
    application = Application.builder().token(TOKEN).build()

    # اضافه کردن دستورات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_admin", set_main_admin))

    # مدیریت پیام‌ها
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))

    # مدیریت callback query ها
    application.add_handler(CallbackQueryHandler(handle_button))

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()

