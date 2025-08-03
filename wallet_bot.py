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

# شروع ربات
async def on_startup(_):
    await init_db()
    print("✅ ربات آماده‌ست.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
