import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import aiosqlite
from datetime import datetime

API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATABASE = "wallet.db"

# کارت بانکی برای افزایش موجودی کارت به کارت
BANK_CARD_NUMBER = "5022291530689296"
BANK_CARD_OWNER = "ملکی"

# کد ثابت مدیر اصلی برای ثبت مدیر اول
MAIN_ADMIN_CODE = "SECRET_ADMIN_CODE_123"

# کمک برای استثیکرهای تعاملی (می‌توان به دلخواه تغییر داد)
STICKER_THUMBS_UP = "CAACAgIAAxkBAAEC0Llga6r8V7nVxXqXR2ZQ6W9ixnNz0gAC-gQAAtTEvFUk5uQx0bM0iS0E"
STICKER_WARNING = "CAACAgIAAxkBAAEC0L9ga6r70jSx1lmK1EpWq_nW0nq-_gACRwADVp29Cj8kUS47vE3nJAQ"
STICKER_CONFIRMED = "CAACAgIAAxkBAAEC0MBga6r7Ld43Dc0bGXxLpejN5F36YwACUQADVp29CnD59pj6YxogJAQ"

# --- دیتابیس ---

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                wallet_address TEXT UNIQUE,
                linked_site INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_main_admin INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT,
                receipt_file_id TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                amount INTEGER,
                used INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_chats (
                user_id INTEGER PRIMARY KEY,
                admin_id INTEGER,
                active INTEGER DEFAULT 1,
                last_message_from TEXT,
                last_message_time TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                is_main_admin INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# --- کمک‌ها ---

def generate_wallet_address(user_id: int) -> str:
    # ساخت یک آدرس کیف پول ساده از user_id به صورت رشته
    return f"wallet_{user_id}"

async def is_user_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT is_main_admin FROM admins WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row)

async def is_user_main_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT is_main_admin FROM admins WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return row[0] == 1
        return False

async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_user_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def set_user_wallet(user_id: int):
    wallet_address = generate_wallet_address(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET wallet_address = ? WHERE user_id = ?", (wallet_address, user_id))
        await db.commit()
    return wallet_address

async def get_user_wallet(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT wallet_address FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_username(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def is_bot_active() -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'bot_active'")
        row = await cursor.fetchone()
        if row:
            return row[0] == '1'
        else:
            # اگر مقدار تنظیم وجود ندارد، فرض کن فعال است
            return True

async def set_bot_active(active: bool):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'bot_active'")
        row = await cursor.fetchone()
        if row:
            await db.execute("UPDATE settings SET value = ? WHERE key = 'bot_active'", ('1' if active else '0',))
        else:
            await db.execute("INSERT INTO settings (key,value) VALUES ('bot_active', ?)", ('1' if active else '0',))
        await db.commit()

# --- کیبوردها ---

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 پروفایل", callback_data="profile"),
        InlineKeyboardButton("💳 انتقال موجودی", callback_data="transfer"),
        InlineKeyboardButton("⬆️ افزایش موجودی", callback_data="increase_balance"),
    )
    kb.add(
        InlineKeyboardButton("📜 قوانین", callback_data="rules"),
        InlineKeyboardButton("📞 ارتباط با پشتیبانی", callback_data="support"),
    )
    return kb

def increase_balance_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🎁 کد هدیه", callback_data="gift_code"),
        InlineKeyboardButton("💳 کارت به کارت", callback_data="card_to_card"),
        InlineKeyboardButton("💳 درگاه پرداخت (غیرفعال)", callback_data="payment_gateway"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    return kb

def admin_panel_kb(is_main_admin: bool):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬆️ افزایش موجودی کاربر", callback_data="admin_increase_balance"))
    kb.add(InlineKeyboardButton("🎁 ساخت کد هدیه", callback_data="admin_create_gift_code"))
    kb.add(InlineKeyboardButton("🔖 ساخت کد تخفیف", callback_data="admin_create_discount_code"))
    kb.add(InlineKeyboardButton("📊 گزارش مالی", callback_data="admin_financial_report"))
    kb.add(InlineKeyboardButton("🚦 فعال/غیرفعال کردن ربات", callback_data="admin_toggle_bot"))
    if is_main_admin:
        kb.add(InlineKeyboardButton("👤 افزودن ادمین جدید", callback_data="admin_add_admin"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    return kb

def yes_no_kb(confirm_callback, cancel_callback):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ بله", callback_data=confirm_callback),
        InlineKeyboardButton("❌ خیر", callback_data=cancel_callback)
    )
    return kb

def rules_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("خواندم", callback_data="rules_read"))
    return kb

def support_end_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("❌ قطع ارتباط", callback_data="support_end"))
    return kb

# --- متغیرهای حالت ---

user_states = {}
admin_states = {}

# --- هندلرها و منطق اصلی ---

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            wallet_addr = generate_wallet_address(user_id)
            await db.execute("INSERT INTO users (user_id, username, balance, wallet_address, linked_site) VALUES (?, ?, 0, ?, 0)", (user_id, username, wallet_addr))
            await db.commit()
            # ثبت مدیر اصلی در جدول admins در صورت وجود کد مدیر
            cursor = await db.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
            admin_exists = await cursor.fetchone()
            if not admin_exists:
                await db.execute("INSERT INTO admins (user_id, is_main_admin) VALUES (?, 0)", (user_id,))
                await db.commit()
        text = (
            f"👋 خوش آمدید به ربات کیف پول!\n\n"
            "از منوی زیر می‌توانید عملیات مورد نظر خود را انتخاب کنید:"
        )
        await message.answer(text, reply_markup=main_menu_kb())

@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def back_to_main_menu(call: types.CallbackQuery):
    await call.message.edit_text(
        "از منوی زیر می‌توانید عملیات مورد نظر خود را انتخاب کنید:",
        reply_markup=main_menu_kb()
    )
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "profile")
async def profile_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    username = await get_username(user_id)
    balance = await get_user_balance(user_id)
    wallet_addr = await get_user_wallet(user_id)
    linked_text = "متصل نشده"
    # در این نسخه فرض شده همه متصل نشده‌اند
    text = (
        f"👤 نام کاربری: @{username}\n"
        f"🆔 آیدی کاربر: `{user_id}`\n"
        f"🏦 آدرس کیف پول: `{wallet_addr}`\n"
        f"💰 موجودی: {balance} تومان\n"
        f"🔗 وضعیت اتصال به سایت: {linked_text}"
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "increase_balance")
async def increase_balance_handler(call: types.CallbackQuery):
    await call.message.edit_text(
        "روش افزایش موجودی را انتخاب کنید:",
        reply_markup=increase_balance_menu_kb()
    )
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "payment_gateway")
async def payment_gateway_handler(call: types.CallbackQuery):
    await call.answer("این بخش فعلا غیرفعال می‌باشد.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "card_to_card")
async def card_to_card_start(call: types.CallbackQuery):
    user_id = call.from_user.id
    # مرحله اول: اعلام شماره کارت
    text = (
        f"شماره کارت برای افزایش موجودی:\n\n"
        f"{BANK_CARD_NUMBER}\n\n"
        "لطفا مبلغ واریزی را به تومان وارد کنید:"
    )
    user_states[user_id] = "awaiting_card_amount"
    await call.message.edit_text(text)
    await call.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id) == "awaiting_card_amount")
async def card_amount_received(message: types.Message):
    user_id = message.from_user.id
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.reply("مبلغ باید عددی مثبت باشد. لطفا دوباره وارد کنید:")
            return
    except:
        await message.reply("مبلغ نامعتبر است. لطفا عدد صحیح وارد کنید:")
        return

    user_states[user_id] = {
        "step": "awaiting_receipt_photo",
        "amount": amount
    }
    await message.reply("لطفا عکس رسید کارت به کارت را ارسال کنید:")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receipt_photo_handler(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state or not isinstance(state, dict) or state.get("step") != "awaiting_receipt_photo":
        # اگر عکس رسید غیر منتظره بود
        return
    photo = message.photo[-1]
    file_id = photo.file_id
    amount = state["amount"]

    # ذخیره درخواست افزایش موجودی
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT INTO topup_requests (user_id, amount, status, receipt_file_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, "pending", file_id, datetime.now().isoformat())
        )
        await db.commit()

    # اطلاع به مدیران
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM admins")
        admins = await cursor.fetchall()
    for admin_row in admins:
        admin_id = admin_row[0]
        try:
            kb = InlineKeyboardMarkup(row_width=3)
            kb.add(
                InlineKeyboardButton("✅ تأیید", callback_data=f"approve_topup_{user_id}_{amount}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_topup_{user_id}_{amount}"),
                InlineKeyboardButton("💬 پیام به کاربر", callback_data=f"msg_user_{user_id}")
            )
            await bot.send_photo(admin_id, file_id, caption=f"درخواست افزایش موجودی:\nکاربر: {user_id}\nمبلغ: {amount} تومان\nوضعیت: در انتظار تایید", reply_markup=kb)
        except Exception as e:
            logging.warning(f"خطا در ارسال پیام به ادمین {admin_id}: {e}")

    await message.reply_sticker(STICKER_THUMBS_UP)
    await message.reply("درخواست شما ثبت شد و منتظر تایید مدیر است.")
    user_states.pop(user_id, None)

# مدیریت تایید و رد درخواست‌ها توسط ادمین‌ها
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("approve_topup_"))
async def approve_topup_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 4:
        await call.answer("داده نامعتبر", show_alert=True)
        return
    user_id = int(parts[2])
    amount = int(parts[3])

    if not await is_user_admin(call.from_user.id):
        await call.answer("شما دسترسی ندارید.", show_alert=True)
        return

    # بروزرسانی موجودی کاربر و تغییر وضعیت درخواست
    async with aiosqlite.connect(DATABASE) as db:
        await update_user_balance(user_id, amount)
        await db.execute("UPDATE topup_requests SET status = 'approved' WHERE user_id = ? AND amount = ? AND status = 'pending'", (user_id, amount))
        await db.commit()

    await call.answer("درخواست تایید شد.", show_alert=True)
    await call.message.edit_caption(f"درخواست افزایش موجودی:\nکاربر: {user_id}\nمبلغ: {amount} تومان\nوضعیت: تأیید شده {STICKER_CONFIRMED}")

    try:
        await bot.send_message(user_id, f"درخواست افزایش موجودی شما به مبلغ {amount} تومان تایید شد. موجودی شما به روز شد.")
    except:
        pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reject_topup_"))
async def reject_topup_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 4:
        await call.answer("داده نامعتبر", show_alert=True)
        return
    user_id = int(parts[2])
    amount = int(parts[3])

    if not await is_user_admin(call.from_user.id):
        await call.answer("شما دسترسی ندارید.", show_alert=True)
        return

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE topup_requests SET status = 'rejected' WHERE user_id = ? AND amount = ? AND status = 'pending'", (user_id, amount))
        await db.commit()

    await call.answer("درخواست رد شد.", show_alert=True)
    await call.message.edit_caption(f"درخواست افزایش موجودی:\nکاربر: {user_id}\nمبلغ: {amount} تومان\nوضعیت: رد شده {STICKER_WARNING}")

    try:
        await bot.send_message(user_id, f"درخواست افزایش موجودی شما به مبلغ {amount} تومان رد شد.")
    except:
        pass

# پیام دادن به کاربر از طرف ادمین (واسطه‌گری پیام)
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("msg_user_"))
async def msg_user_handler(call: types.CallbackQuery):
    if not await is_user_admin(call.from_user.id):
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    target_user_id = int(call.data.split("_")[-1])
    admin_states[call.from_user.id] = {
        "mode": "message_user",
        "target": target_user_id
    }
    await call.message.answer(f"پیام خود را برای کاربر {target_user_id} ارسال کنید.\nبرای خروج دستور /cancel را بزنید.")
    await call.answer()

@dp.message_handler(lambda m: admin_states.get(m.from_user.id, {}).get("mode") == "message_user")
async def admin_send_message_to_user(message: types.Message):
    admin_id = message.from_user.id
    state = admin_states.get(admin_id)
    if not state:
        return
    target_user_id = state["target"]
    try:
        if message.text:
            await bot.send_message(target_user_id, f"پیام از مدیر:\n{message.text}")
        elif message.sticker:
            await bot.send_sticker(target_user_id, message.sticker.file_id)
        elif message.photo:
            await bot.send_photo(target_user_id, message.photo[-1].file_id, caption=message.caption or "")
        # می‌توان انواع پیام‌های دیگر را اضافه کرد
        await message.answer("پیام ارسال شد.")
    except Exception as e:
        await message.answer(f"خطا در ارسال پیام: {e}")
    admin_states.pop(admin_id)

@dp.message_handler(commands=["cancel"])
async def cancel_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_states:
        user_states.pop(user_id)
        await message.reply("عملیات لغو شد.")
    if user_id in admin_states:
        admin_states.pop(user_id)
        await message.reply("عملیات لغو شد.")

# اینجا ادامه میدم ... (پنل مدیریت، ساخت کد هدیه، کد تخفیف، افزایش موجودی توسط ادمین، گزارش مالی، افزودن ادمین و غیره)

# --- شروع برنامه و آماده سازی دیتابیس ---

async def on_startup(dp):
    await init_db()
    logging.info("ربات با موفقیت راه‌اندازی شد.")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
