import os
import logging
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_CODE = "221100"  # کدی برای ثبت مدیر
CARD_NUMBER = "5022291530689296"
CARD_NAME = "به نام ملکی"

bot = Bot(token=API_TOKEN, parse_mode='HTML')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# وضعیت‌ها
class TopUpFSM(StatesGroup):
    amount = State()
    waiting_receipt = State()

class SupportFSM(StatesGroup):
    waiting_message = State()
    chatting = State()

# لاگ
logging.basicConfig(level=logging.INFO)

# دیتابیس
async def init_db():
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                wallet_address TEXT,
                is_admin INTEGER DEFAULT 0,
                linked INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                image TEXT
            )
        """)
        await db.commit()

# ساخت آدرس کیف پول
def generate_wallet_address(user_id):
    return f"WALLET-{user_id}"  # نمونه ساده برای شروع

# دکمه‌های منو
async def main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 افزایش موجودی", callback_data="topup"),
        InlineKeyboardButton("🔁 انتقال موجودی", callback_data="transfer"),
        InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
        InlineKeyboardButton("📜 قوانین", callback_data="rules"),
        InlineKeyboardButton("💬 پشتیبانی", callback_data="support")
    )

    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if result and result[0]:
            markup.add(InlineKeyboardButton("🛠 مدیریت", callback_data="admin"))

    return markup

# فرمان استارت
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_نام"

    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user is None:
            wallet_address = generate_wallet_address(user_id)
            await db.execute("INSERT INTO users (user_id, username, wallet_address) VALUES (?, ?, ?)",
                             (user_id, username, wallet_address))
            await db.commit()

    markup = await main_menu(user_id)
    await message.answer_sticker("CAACAgQAAxkBAAEJDaRlYHo4rWz5HXXgZ6eFe3KUVOueOQACfwoAAj-VYFY8EiUPm7uWrDME")
    await message.answer("👋 خوش آمدی به کیف پول رزومیت! از منوی زیر استفاده کن:", reply_markup=markup)

# پروفایل
@dp.callback_query_handler(lambda c: c.data == "profile")
async def show_profile(call: types.CallbackQuery):
    user_id = call.from_user.id
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT username, balance, wallet_address, linked FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()

    text = f"""
👤 نام کاربری: <code>{user[0]}</code>
🆔 آیدی عددی: <code>{user_id}</code>
🏷 آدرس کیف پول: <code>{user[2]}</code>
💰 موجودی: {user[1]} تومان
🔗 اتصال به سایت: {'متصل نشده' if not user[3] else 'متصل شده'}
"""
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📋 کپی آدرس کیف پول", callback_data="copy_wallet"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back")
    )
    await call.message.edit_text(text, reply_markup=markup)

# قوانین
@dp.callback_query_handler(lambda c: c.data == "rules")
async def show_rules(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ خواندم", callback_data="read_rules"))
    await call.message.edit_text("""
📜 <b>قوانین استفاده:</b>
1. استفاده غیرمجاز ممنوع است.
2. مسئولیت امنیت کیف پول با شماست.
3. در صورت تخلف، حساب مسدود می‌شود.
    """, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "read_rules")
async def hide_rules(call: types.CallbackQuery):
    await call.message.delete()

# بازگشت به منو
@dp.callback_query_handler(lambda c: c.data == "back")
async def go_back(call: types.CallbackQuery):
    markup = await main_menu(call.from_user.id)
    await call.message.edit_text("👋 از منوی زیر استفاده کن:", reply_markup=markup)

# افزایش موجودی
@dp.callback_query_handler(lambda c: c.data == "topup")
async def ask_topup_method(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💳 کارت به کارت", callback_data="topup_card")
    )
    await call.message.edit_text("لطفاً روش افزایش موجودی را انتخاب کنید:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == "topup_card")
async def ask_amount(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        admin_check = await cursor.fetchone()
        if admin_check and admin_check[0]:
            await call.answer("شما مدیر هستید و نیاز به واریز ندارید.", show_alert=True)
            return

    await TopUpFSM.amount.set()
    await call.message.edit_text("مبلغ موردنظر برای واریز را (به تومان) وارد کنید:")

@dp.message_handler(state=TopUpFSM.amount)
async def get_topup_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        await state.update_data(amount=amount)
        await message.answer(f"✅ مبلغ {amount} تومان انتخاب شد. شماره کارت:")
        await message.answer(f"💳 <code>{CARD_NUMBER}</code>\n🧾 {CARD_NAME}", reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📋 کپی شماره کارت", callback_data="copy_card"),
            InlineKeyboardButton("✅ واریز شد", callback_data="paid")
        ))
        await TopUpFSM.waiting_receipt.set()
    except ValueError:
        await message.reply("لطفاً فقط مبلغ را به صورت عددی وارد کنید.")

@dp.callback_query_handler(lambda c: c.data == "paid", state=TopUpFSM.waiting_receipt)
async def ask_receipt(call: types.CallbackQuery):
    await call.message.edit_reply_markup()
    await call.message.answer("🖼 لطفاً تصویر رسید بانکی را ارسال کنید.")

@dp.message_handler(content_types=types.ContentType.PHOTO, state=TopUpFSM.waiting_receipt)
async def receive_receipt(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    photo = message.photo[-1].file_id
    data = await state.get_data()
    amount = data['amount']

    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("INSERT INTO receipts (user_id, amount, image) VALUES (?, ?, ?)", (user_id, amount, photo))
        await db.commit()

        cursor = await db.execute("SELECT user_id FROM users WHERE is_admin = 1")
        admins = await cursor.fetchall()

    for admin in admins:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ تایید واریزی", callback_data=f"approve_{user_id}_{amount}"),
            InlineKeyboardButton("❌ فیک", callback_data=f"fake_{user_id}"),
            InlineKeyboardButton("✉ پیام به کاربر", callback_data=f"msgto_{user_id}")
        )
        await bot.send_photo(admin[0], photo, caption=f"📥 رسید واریزی جدید:\nمبلغ: {amount} تومان\nاز طرف: {user_id}", reply_markup=markup)

    await message.answer("رسید شما برای بررسی ارسال شد. منتظر تایید توسط پشتیبانی باشید.")
    await state.finish()

# ثبت مدیر
@dp.message_handler(commands=['setadmin'])
async def set_admin(message: types.Message):
    if message.get_args() == ADMIN_CODE:
        async with aiosqlite.connect("wallet.db") as db:
            await db.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (message.from_user.id,))
            await db.commit()
        await message.reply("شما به عنوان مدیر ثبت شدید ✅")
    else:
        await message.reply("کد وارد شده نادرست است ❌")

# شروع ربات
async def on_startup(_):
    await init_db()
    print("✅ ربات آماده است.")

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
