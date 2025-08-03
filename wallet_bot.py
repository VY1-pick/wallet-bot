import sqlite3
from telegram import Update, ReplyKeyboardMarkup, ForceReply
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# شناسه مدیر اصلی
ADMIN_PIN = "adminpixit"

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
    # تنظیمات پیش‌فرض
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('robot_status', 'active')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_number', '5022291530689296')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rate', '1000')")
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

# شروع ربات و منو
async def start(update: Update, context: CallbackContext) -> None:
    # چک کردن مدیر اصلی
    if not check_main_admin():
        # ارسال پیام و درخواست کد امنیتی برای ثبت مدیر
        reply_markup = ForceReply(selective=True)
        await update.message.reply_text(
            "مدیر اصلی مشخص نشده است. لطفاً کد امنیتی را وارد کنید.",
            reply_markup=reply_markup
        )
        return

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

# دریافت کد امنیتی برای ثبت مدیر اصلی
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

# مدیریت ورودی‌ها و دکمه‌ها
async def handle_button(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    message = update.message.text

    if message == "افزایش موجودی":
        await update.message.reply_text("برای افزایش موجودی روش مورد نظر خود را انتخاب کنید.")
    elif message == "مشاهده موجودی":
        await update.message.reply_text(f"موجودی شما: {get_balance(user_id)} PXT")
    elif message == "پروفایل":
        await update.message.reply_text("اطلاعات پروفایل شما:")
    elif message == "راهنما":
        await update.message.reply_text("راهنما: استفاده از ربات بسیار ساده است. با دکمه‌ها اقدام کنید.")
    elif message == "تنظیمات":
        await update.message.reply_text("تنظیمات ربات شما:")
    else:
        await update.message.reply_text("دکمه نامعتبری انتخاب شده است.")

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

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()
