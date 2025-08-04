import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
import logging
import os

# تنظیمات اولیه
API_TOKEN = os.getenv('API_TOKEN')  # متغیر محیطی توکن ربات

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ایجاد دیتابیس
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)''')
    conn.commit()
    conn.close()

# گرفتن موجودی کاربر
def get_balance(user_id):
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id=?', (user_id,))
    balance = c.fetchone()
    conn.close()
    return balance[0] if balance else 0

# افزودن موجودی
def add_balance(user_id, amount):
    current_balance = get_balance(user_id)
    new_balance = current_balance + amount
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    if get_balance(user_id) == 0:
        c.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, new_balance))
    else:
        c.execute('UPDATE users SET balance=? WHERE user_id=?', (new_balance, user_id))
    conn.commit()
    conn.close()

# دستور شروع
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("سلام! خوش اومدی به ربات کیف پول دیجیتال.\nبرای مشاهده موجودی از دستور /balance استفاده کن.")

# دستور مشاهده موجودی
@dp.message_handler(commands=['balance'])
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    balance = get_balance(user_id)
    await message.answer(f"موجودی شما: {balance} PXT")

# دستور انتقال وجه
@dp.message_handler(commands=['transfer'])
async def cmd_transfer(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args().split()

    if len(args) != 2:
        await message.answer("لطفاً به شکل زیر درخواست رو وارد کن:\n/transfer <مقدار> <شناسه گیرنده>")
        return
    
    try:
        amount = int(args[0])
        recipient_id = int(args[1])
    except ValueError:
        await message.answer("لطفاً مقادیر صحیح وارد کنید.")
        return

    if amount <= 0:
        await message.answer("مقدار باید بیشتر از صفر باشد.")
        return
    
    sender_balance = get_balance(user_id)
    if sender_balance < amount:
        await message.answer("موجودی کافی نیست.")
        return

    # انتقال وجه
    add_balance(user_id, -amount)
    add_balance(recipient_id, amount)
    await message.answer(f"موفقیت! {amount} PXT به کاربر {recipient_id} منتقل شد.")

# دستور وارد کردن کد هدیه
@dp.message_handler(commands=['gift'])
async def cmd_gift(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()

    if len(args) != 1:
        await message.answer("لطفاً کد هدیه رو وارد کن.")
        return
    
    code = args[0]
    if code == "GIFT123":  # مثلاً کد هدیه پیش‌فرض
        add_balance(user_id, 1000)  # افزودن 1000 PXT به موجودی
        await message.answer("کد هدیه معتبر بود! 1000 PXT به موجودی شما افزوده شد.")
    else:
        await message.answer("کد هدیه نامعتبر است.")

# اجرای ربات
if __name__ == '__main__':
    create_db()  # ساخت دیتابیس
    executor.start_polling(dp, skip_updates=True)
