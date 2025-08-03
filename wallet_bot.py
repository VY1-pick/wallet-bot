import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# شناسه مدیر اصلی
ADMIN_PIN = "AdminPiXiT"

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

# ارسال استیکر
def send_sticker(update, sticker_id):
    try:
        update.message.reply_sticker(sticker_id)
    except Exception as e:
        print("Error sending sticker:", e)

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
        await update.message.reply_text("مدیر اصلی مشخص نشده است. ربات غیر فعال است.")
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # ثبت‌نام کاربر
    register_user(user_id, username)

    # ارسال استیکر خوشامدگویی
    send_sticker(update, "CAACAgUAAxkBAAEBz8FlB8VsdXZZRax7q82yWYNrYm9rWwACFwAD9XgBEbC2P7ahp1EuHgQ")

    # ایجاد منوی شیشه‌ای با دو ستون
    keyboard = [
        [InlineKeyboardButton("افزایش موجودی", callback_data='top_up'), InlineKeyboardButton("مشاهده موجودی", callback_data='balance')],
        [InlineKeyboardButton("پروفایل", callback_data='profile'), InlineKeyboardButton("راهنما", callback_data='help')],
        [InlineKeyboardButton("تنظیمات", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام خوشامد
    await update.message.reply_text(
        f"سلام {username}! خوش آمدید به ربات کیف پول PXT. برای شروع یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=reply_markup
    )

# مشخص کردن مدیر اصلی
async def set_main_admin(update: Update, context: CallbackContext) -> None:
    if context.args:
        main_admin_username = context.args[0]
        main_admin_user_id = update.message.from_user.id
        
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute("INSERT INTO main_admin (username, user_id) VALUES (?, ?)", (main_admin_username, main_admin_user_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"مدیر اصلی با نام کاربری {main_admin_username} تنظیم شد.")
    else:
        await update.message.reply_text("لطفاً نام کاربری مدیر اصلی را وارد کنید.")

# منو تنظیمات
async def settings(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("فعال/غیرفعال کردن ربات", callback_data='toggle_robot'), InlineKeyboardButton("تغییر شماره کارت", callback_data='change_card')],
        [InlineKeyboardButton("تنظیم نرخ تبدیل", callback_data='change_rate')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مدیر عزیز، لطفاً یکی از گزینه‌ها را انتخاب کنید.", reply_markup=reply_markup)

# مدیریت CallbackQuery برای دکمه‌ها
async def handle_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # پاسخ به callback query
    callback_data = query.data

    if callback_data == 'top_up':
        await update.message.reply_text("برای افزایش موجودی روش مورد نظر خود را انتخاب کنید.")
    elif callback_data == 'balance':
        await update.message.reply_text(f"موجودی شما: {get_balance(update.message.from_user.id)} PXT")
    elif callback_data == 'profile':
        await profile(update, context)
    elif callback_data == 'help':
        await update.message.reply_text("راهنما: راهنمای استفاده از ربات.")
    elif callback_data == 'settings':
        await settings(update, context)
    elif callback_data == 'toggle_robot':
        await toggle_robot(update, context)
    elif callback_data == 'change_card':
        await change_card(update, context)
    elif callback_data == 'change_rate':
        await change_rate(update, context)

# پروفایل کاربر
async def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    balance = get_balance(user_id)
    
    # دریافت آدرس کیف پول و اطلاعات دیگر
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT user_id, username FROM users WHERE user_id = ?', (user_id,))
    user_info = c.fetchone()
    conn.close()

    # اطلاعات پروفایل کاربر
    profile_text = f"پروفایل شما:\n\n"
    profile_text += f"نام کاربری: {username}\n"
    profile_text += f"موجودی: {balance} PXT\n"
    profile_text += f"شناسه کاربری: {user_info[0]}\n"  # نمایش شناسه کاربری
    profile_text += f"آدرس کیف پول: ناتمام (اضافه کردن امکان ذخیره آدرس کیف پول در آینده)"
    
    # ارسال پروفایل به کاربر
    await update.message.reply_text(profile_text)

# تابع اصلی
def main():
    create_db()  # ساخت دیتابیس

    # ایجاد Application
    application = Application.builder().token(TOKEN).build()

    # اضافه کردن دستورات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("set_admin", set_main_admin))

    # مدیریت callback query ها
    application.add_handler(CallbackQueryHandler(handle_button))

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()


