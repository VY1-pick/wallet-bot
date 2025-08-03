import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Sticker
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
import re

# توکن ربات تلگرام
TOKEN = "7092562641:AAF58jJ5u_CB6m7Y2803R8Cx9bdfymZgYuA"

# ایجاد دیتابیس و جدول برای کاربران و رسیدها
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER,
            image_url TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY,
            user_id INTEGER
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
        [InlineKeyboardButton("راهنما", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام خوشامد
    await update.message.reply_text(
        f"سلام {username}! خوش آمدید به ربات کیف پول PXT. برای شروع یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=reply_markup
    )

# منو افزایش موجودی
async def top_up(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("درگاه پرداخت", callback_data='payment_gateway')],
        [InlineKeyboardButton("کارت به کارت", callback_data='card_to_card')],
        [InlineKeyboardButton("کد هدیه", callback_data='gift_code')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("برای افزایش موجودی یکی از گزینه‌ها را انتخاب کنید.", reply_markup=reply_markup)

# کارت به کارت
async def card_to_card(update: Update, context: CallbackContext) -> None:
    # مرحله 1: مبلغ
    keyboard = [
        [InlineKeyboardButton("بازگشت", callback_data='top_up')],
        [InlineKeyboardButton("مرحله بعد", callback_data='card_amount')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً مبلغ مورد نظر خود را وارد کنید.", reply_markup=reply_markup)

# دریافت مبلغ کارت به کارت
async def card_amount(update: Update, context: CallbackContext) -> None:
    # مرحله 2: شماره کارت
    keyboard = [
        [InlineKeyboardButton("بازگشت", callback_data='top_up')],
        [InlineKeyboardButton("واریز شد", callback_data='deposit')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً شماره کارت خود را وارد کنید.", reply_markup=reply_markup)

# دریافت رسید کارت به کارت
async def deposit(update: Update, context: CallbackContext) -> None:
    # مرحله 3: ارسال رسید تصویری
    await update.message.reply_text("لطفاً رسید پرداخت خود را ارسال کنید.")

# مدیریت رسیدها
async def manage_receipts(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("تایید رسید", callback_data='approve_receipt')],
        [InlineKeyboardButton("رسید فیک", callback_data='fake_receipt')],
        [InlineKeyboardButton("پیام به کاربر", callback_data='message_user')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("مدیر محترم، لطفاً رسیدها را مدیریت کنید.", reply_markup=reply_markup)

# پروفایل کاربر
async def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    balance = get_balance(user_id)
    profile_text = f"پروفایل شما:\n\n"
    profile_text += f"نام کاربری: {username}\n"
    profile_text += f"موجودی: {balance} PXT\n"
    await update.message.reply_text(profile_text)

# راهنما
async def help(update: Update, context: CallbackContext) -> None:
    help_text = (
        "راهنما:\n\n"
        "1. مشاهده موجودی: موجودی کیف پول خود را مشاهده کنید.\n"
        "2. افزایش موجودی: موجودی خود را با روش‌های مختلف افزایش دهید.\n"
        "3. پروفایل: مشاهده اطلاعات پروفایل خود."
    )
    await update.message.reply_text(help_text)

# ثبت مدیر اصلی
async def set_admin(update: Update, context: CallbackContext) -> None:
    # فقط مدیر اصلی می‌تواند مدیر جدید ایجاد کند.
    user_id = update.message.from_user.id
    # بررسی اینکه کاربر مدیر اصلی است
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('INSERT INTO admins (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("شما به عنوان مدیر اصلی ثبت شدید!")

# افزودن مدیر جدید
async def add_admin(update: Update, context: CallbackContext) -> None:
    if context.args:
        new_admin_id = int(context.args[0])
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute('INSERT INTO admins (user_id) VALUES (?)', (new_admin_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"مدیر جدید با شناسه {new_admin_id} افزوده شد.")
    else:
        await update.message.reply_text("لطفاً شناسه کاربری مدیر جدید را وارد کنید.")

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

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()
