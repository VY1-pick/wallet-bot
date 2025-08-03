import os
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
import asyncio

API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- Database Init ---
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

# --- Keyboards ---
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 موجودی", callback_data="balance"),
        InlineKeyboardButton("➕ شارژ کیف پول", callback_data="topup"),
        InlineKeyboardButton("🔁 کارت به کارت", callback_data="transfer")
    )
    return kb

# --- Handlers ---
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

    await message.reply("👋 خوش اومدی به کیف پول دیجیتال! از منوی زیر استفاده کن:", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data == "balance")
async def cb_balance(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if result:
            await callback.message.answer(f"💰 موجودی فعلی: {result[0]} تومان")
        else:
            await callback.message.answer("❗ حسابی برای شما پیدا نشد. لطفاً /start رو بزنید.")

@dp.callback_query_handler(lambda c: c.data == "topup")
async def cb_topup(callback: types.CallbackQuery):
    await callback.message.answer("برای شارژ کیف پول دستور رو به این صورت وارد کن:\n`/topup 20000`", parse_mode="Markdown")

@dp.message_handler(commands=['topup'])
async def topup_cmd(message: types.Message):
    user_id = message.from_user.id
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError()
        amount = int(parts[1])
        if amount <= 0:
            raise ValueError()

        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()
            if not user:
                await message.reply("❗ ابتدا با /start کیف پول بسازید.")
                return

            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

        await message.reply(f"✅ مبلغ {amount} تومان با موفقیت شارژ شد.")

    except:
        await message.reply("❌ لطفاً به این صورت وارد کنید:\n`/topup 20000`", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "transfer")
async def cb_transfer(callback: types.CallbackQuery):
    await callback.message.answer("برای کارت به کارت دستور رو به این صورت بفرست:\n`/transfer user_id amount`\nمثال: `/transfer 123456789 5000`", parse_mode="Markdown")

@dp.message_handler(commands=['transfer'])
async def transfer_cmd(message: types.Message):
    user_id = message.from_user.id
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError()
        target_id = int(parts[1])
        amount = int(parts[2])
        if amount <= 0:
            raise ValueError()

        async with aiosqlite.connect("wallet.db") as db:
            # بررسی حساب مبدا
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            sender = await cursor.fetchone()
            if not sender:
                await message.reply("❗ ابتدا با /start کیف پول بسازید.")
                return
            if sender[0] < amount:
                await message.reply("❌ موجودی کافی نیست.")
                return

            # بررسی حساب مقصد
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (target_id,))
            recipient = await cursor.fetchone()
            if not recipient:
                await message.reply("❌ حساب مقصد پیدا نشد یا هنوز کیف پول نساخته.")
                return

            # انجام تراکنش
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            await db.commit()

        await message.reply(f"✅ مبلغ {amount} تومان به کاربر {target_id} منتقل شد.")

    except:
        await message.reply("❌ لطفاً دستور را به صورت صحیح وارد کنید:\n`/transfer user_id amount`", parse_mode="Markdown")

# --- Startup ---
async def on_startup(_):
    await init_db()
    print("✅ ربات آماده‌ست.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
