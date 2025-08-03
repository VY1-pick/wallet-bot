import sqlite3
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import os

# ====== تنظیمات ======
TOKEN = os.getenv("API_TOKEN")

# ایجاد دیتابیس و جدول برای کاربران
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ثبت‌نام کاربر جدید
def register_user(user_id, username):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

# گرفتن موجودی کاربر
def get_balance(user_id):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = c.fetchone()
    conn.close()
    return balance[0] if balance else 0

# به‌روزرسانی موجودی کاربر
def update_balance(user_id, amount):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# تابع شروع برای ثبت‌نام
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # ثبت‌نام کاربر در دیتابیس
    register_user(user_id, username)

    update.message.reply_text(f"سلام {username}! شما با موفقیت ثبت‌نام شدید. موجودی شما: {get_balance(user_id)} PXT")

# تابع برای نمایش موجودی
def balance(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    balance = get_balance(user_id)
    update.message.reply_text(f"موجودی شما: {balance} PXT")

# تابع برای ارسال PXT به کاربر دیگر
def send(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    amount = int(context.args[0])  # مقدار PXT که میخواهند ارسال کنند

    if get_balance(user_id) >= amount:
        update_balance(user_id, -amount)
        update.message.reply_text(f"{amount} PXT با موفقیت ارسال شد. موجودی شما: {get_balance(user_id)} PXT")
    else:
        update.message.reply_text("موجودی کافی برای انجام این تراکنش ندارید.")

def main():
    create_db()  # ساخت دیتابیس

    # ایجاد آپدیت کننده
    updater = Updater(TOKEN)

    # دریافت دیسپاچر
    dispatcher = updater.dispatcher

    # اضافه کردن دستورات
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("send", send))

    # شروع ربات
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
