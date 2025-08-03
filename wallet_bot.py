import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# ایجاد دیتابیس و جدول برای کاربران
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            transactions TEXT DEFAULT ''
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

# افزودن تراکنش
def add_transaction(user_id, amount):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT transactions FROM users WHERE user_id = ?', (user_id,))
    transactions = c.fetchone()[0]
    transactions += f"{amount} PXT\n"
    c.execute('UPDATE users SET transactions = ? WHERE user_id = ?', (transactions, user_id))
    conn.commit()
    conn.close()

# پیام خوشامد با منوی شیشه‌ای
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # ثبت‌نام کاربر
    register_user(user_id, username)
    
    # ایجاد منوی شیشه‌ای
    keyboard = [
        [InlineKeyboardButton("مشاهده موجودی", callback_data='balance')],
        [InlineKeyboardButton("تاریخچه تراکنش‌ها", callback_data='transactions')],
        [InlineKeyboardButton("ارسال PXT", callback_data='send')],
        [InlineKeyboardButton("راهنما", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام خوشامد
    await update.message.reply_text(
        f"سلام {username}! خوش آمدید به ربات کیف پول PXT. با این ربات می‌توانید موجودی خود را مشاهده کرده و تراکنش انجام دهید. \n\nبرای شروع، یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=reply_markup
    )

# منو: موجودی
async def balance(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    balance = get_balance(user_id)
    await update.message.reply_text(f"موجودی شما: {balance} PXT")

# منو: تاریخچه تراکنش‌ها
async def transactions(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT transactions FROM users WHERE user_id = ?', (user_id,))
    transactions = c.fetchone()[0]
    conn.close()
    
    if transactions:
        await update.message.reply_text(f"تاریخچه تراکنش‌ها:\n{transactions}")
    else:
        await update.message.reply_text("تراکنشی برای نمایش وجود ندارد.")

# منو: ارسال PXT
async def send(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if context.args:
        amount = int(context.args[0])
        if get_balance(user_id) >= amount:
            update_balance(user_id, -amount)
            add_transaction(user_id, -amount)
            await update.message.reply_text(f"{amount} PXT با موفقیت ارسال شد. موجودی شما: {get_balance(user_id)} PXT")
        else:
            await update.message.reply_text("موجودی کافی برای انجام این تراکنش ندارید.")
    else:
        await update.message.reply_text("لطفاً مقداری برای ارسال وارد کنید.")

# منو: راهنما
async def help(update: Update, context: CallbackContext) -> None:
    help_text = (
        "راهنما:\n\n"
        "1. مشاهده موجودی: موجودی کیف پول خود را مشاهده کنید.\n"
        "2. تاریخچه تراکنش‌ها: لیستی از تمامی تراکنش‌های شما.\n"
        "3. ارسال PXT: می‌توانید PXT به دیگران ارسال کنید."
    )
    await update.message.reply_text(help_text)

# تابع اصلی
def main():
    create_db()  # ساخت دیتابیس

    # ایجاد Application
    application = Application.builder().token(TOKEN).build()

    # اضافه کردن دستورات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("send", send))
    application.add_handler(CommandHandler("help", help))

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()
