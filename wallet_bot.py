import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# ایجاد دیتابیس و جدول برای کاربران، رسیدها و تنظیمات
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

# شروع ربات و منو
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # ثبت‌نام کاربر
    register_user(user_id, username)

    # ارسال استیکر خوشامدگویی
    send_sticker(update, "CAACAgUAAxkBAAEBz8FlB8VsdXZZRax7q82yWYNrYm9rWwACFwAD9XgBEbC2P7ahp1EuHgQ")

    # ایجاد منوی شیشه‌ای
    keyboard = [
        [InlineKeyboardButton("افزایش موجودی", callback_data='top_up')],
        [InlineKeyboardButton("مشاهده موجودی", callback_data='balance')],
        [InlineKeyboardButton("پروفایل", callback_data='profile')],
        [InlineKeyboardButton("راهنما", callback_data='help')],
        [InlineKeyboardButton("تنظیمات", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام خوشامد
    await update.message.reply_text(
        f"سلام {username}! خوش آمدید به ربات کیف پول PXT. برای شروع یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=reply_markup
    )

# منو تنظیمات
async def settings(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("فعال/غیرفعال کردن ربات", callback_data='toggle_robot')],
        [InlineKeyboardButton("تغییر شماره کارت", callback_data='change_card')],
        [InlineKeyboardButton("تنظیم نرخ تبدیل", callback_data='change_rate')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مدیر عزیز، لطفاً یکی از گزینه‌ها را انتخاب کنید.", reply_markup=reply_markup)

# تغییر وضعیت ربات (فعال/غیرفعال)
async def toggle_robot(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'robot_status'")
    current_status = c.fetchone()[0]
    new_status = 'inactive' if current_status == 'active' else 'active'
    c.execute("UPDATE settings SET value = ? WHERE key = 'robot_status'", (new_status,))
    conn.commit()
    conn.close()
    status_text = f"ربات {new_status} شد."
    await update.message.reply_text(status_text)

# تغییر شماره کارت
async def change_card(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("لطفاً شماره کارت جدید را وارد کنید:")

# دریافت شماره کارت جدید
async def set_new_card(update: Update, context: CallbackContext) -> None:
    new_card = update.message.text
    if re.match(r"^\d{16}$", new_card):  # بررسی شماره کارت
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'card_number'", (new_card,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"شماره کارت به {new_card} تغییر یافت.")
    else:
        await update.message.reply_text("شماره کارت وارد شده معتبر نیست. لطفاً یک شماره کارت معتبر وارد کنید.")

# تغییر نرخ تبدیل
async def change_rate(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("لطفاً نرخ تبدیل جدید (تومان به PXT) را وارد کنید:")

# دریافت نرخ تبدیل جدید
async def set_new_rate(update: Update, context: CallbackContext) -> None:
    new_rate = update.message.text
    if new_rate.isdigit():
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'rate'", (new_rate,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"نرخ تبدیل به {new_rate} تومان برای هر PXT تغییر یافت.")
    else:
        await update.message.reply_text("لطفاً یک نرخ معتبر وارد کنید.")

# تابع اصلی
def main():
    create_db()  # ساخت دیتابیس

    # ایجاد Application
    application = Application.builder().token(TOKEN).build()

    # اضافه کردن دستورات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("add_admin", add_admin))

    # مدیریت ورودی‌ها
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_card))  # برای تغییر شماره کارت
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_rate))  # برای تغییر نرخ تبدیل

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()
