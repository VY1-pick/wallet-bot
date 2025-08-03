import os
import logging
from aiogram import Bot, Dispatcher, executor, types
import aiosqlite
import asyncio

API_TOKEN = os.getenv("API_TOKEN")

# لاگ
logging.basicConfig(level=logging.INFO)

# ربات
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# راه‌اندازی دیتابیس
async def init_db():
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# فرمان /start
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()

        if user is None:
            await db.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)",
                             (user_id, username, 0))
            await db.commit()
            await message.reply("👋 خوش اومدی! حساب کیف پولت ساخته شد.")
        else:
            await message.reply("👋 قبلاً ثبت‌نام کردی.")

# فرمان /balance
@dp.message_handler(commands=['balance'])
async def balance_cmd(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()

        if result:
            balance = result[0]
            await message.reply(f"💰 موجودی شما: {balance} تومان")
        else:
            await message.reply("❗ حسابی برای شما پیدا نشد. لطفاً /start رو بزنید.")

# فرمان /topup
@dp.message_handler(commands=['topup'])
async def topup_cmd(message: types.Message):
    user_id = message.from_user.id
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("فرمت نادرست")

        amount = int(parts[1])
        if amount <= 0:
            raise ValueError("مقدار نامعتبر")

        async with aiosqlite.connect("wallet.db") as db:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

        await message.reply(f"✅ مبلغ {amount} تومان با موفقیت به کیف پول شما اضافه شد.")

    except ValueError:
        await message.reply("❌ لطفاً دستور را به این صورت وارد کنید:\n`/topup 20000`", parse_mode="Markdown")


# شروع ربات
async def on_startup(_):
    await init_db()
    print("✅ ربات آماده‌ست.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
