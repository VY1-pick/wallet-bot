import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from datetime import datetime

API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# وضعیت کلی ربات
BOT_STATUS_FILE = "bot_status.txt"

# دیکشنری برای نگهداری وضعیت کاربران و مدیران در حافظه موقت (برای سادگی)
user_states = {}  # {user_id: {state: ..., data: {...}}}

# --- بانک اطلاعاتی ---
async def init_db():
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                wallet TEXT UNIQUE,
                balance INTEGER DEFAULT 0,
                username TEXT,
                linked_site INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                is_super INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                amount INTEGER,
                used INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                percent INTEGER,
                used_by TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_wallet TEXT,
                amount INTEGER,
                type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def is_admin(user_id):
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_super FROM admins WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res is not None

async def is_super_admin(user_id):
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_super FROM admins WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res is not None and res[0] == 1

async def get_user_wallet(user_id):
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res[0] if res else None

async def create_user_if_not_exists(user_id, username):
    async with aiosqlite.connect("wallet.db") as db:
        wallet = f"wallet_{user_id}"  # آدرس کیف پول ساده
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if not res:
            await db.execute("INSERT INTO users (user_id, wallet, username) VALUES (?, ?, ?)",
                             (user_id, wallet, username))
            await db.commit()
        return wallet

async def get_user_balance(user_id):
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res[0] if res else 0

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def update_user_balance_set(user_id, amount):
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_bot_status():
    if not os.path.exists(BOT_STATUS_FILE):
        return "active"
    with open(BOT_STATUS_FILE, "r") as f:
        return f.read().strip()

async def set_bot_status(status):
    with open(BOT_STATUS_FILE, "w") as f:
        f.write(status)

# --- کیبوردهای اصلی ---

def main_menu_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("پروفایل 👤", callback_data="menu_profile"),
        InlineKeyboardButton("افزایش موجودی 💰", callback_data="menu_topup"),
        InlineKeyboardButton("انتقال موجودی 🔄", callback_data="menu_transfer"),
        InlineKeyboardButton("ارتباط با پشتیبانی 📞", callback_data="menu_support"),
        InlineKeyboardButton("قوانین ⚠️", callback_data="menu_rules")
    )
    return kb

def topup_method_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("کارت به کارت", callback_data="topup_card_to_card"),
        InlineKeyboardButton("کد هدیه", callback_data="topup_gift_code"),
        InlineKeyboardButton("درگاه پرداخت (غیرفعال)", callback_data="topup_payment_gateway")
    )
    return kb

def admin_main_menu_keyboard(is_super=False):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("افزایش موجودی کاربران", callback_data="admin_increase_balance"),
        InlineKeyboardButton("ساخت کد هدیه", callback_data="admin_create_gift_code"),
        InlineKeyboardButton("ساخت کد تخفیف", callback_data="admin_create_discount_code"),
        InlineKeyboardButton("گزارش مالی", callback_data="admin_financial_report"),
        InlineKeyboardButton("فعال/غیرفعال کردن ربات", callback_data="admin_toggle_bot")
    )
    if is_super:
        kb.add(
            InlineKeyboardButton("افزودن ادمین جدید", callback_data="admin_add_new_admin")
        )
    return kb

# --- هندلر استارت ---
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    await create_user_if_not_exists(user_id, username)

    # ثبت مدیر اگر ربات مدیر ندارد و دستور ثبت مدیر با کد تایید زده شده باشد
    args = message.get_args()
    if args == "registeradmincode123":  # کد ثابت برای ثبت مدیر اصلی (تو عوضش کن)
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute("SELECT user_id FROM admins")
            res = await cursor.fetchone()
            if not res:
                await db.execute("INSERT INTO admins (user_id, is_super) VALUES (?, 1)", (user_id,))
                await db.commit()
                await message.answer("شما به عنوان مدیر اصلی ثبت شدید.")
                return
            else:
                await message.answer("مدیر اصلی قبلاً ثبت شده است.")
                return

    bot_status = await get_bot_status()
    if bot_status == "inactive":
        await message.answer("ربات فعلاً غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return

    kb = main_menu_keyboard()
    await message.answer(
        f"سلام {username} عزیز!\nبه ربات کیف پول خوش آمدید.\nلطفاً از منوی زیر استفاده کنید.",
        reply_markup=kb
    )

# --- هندلر کلیک روی دکمه های منو ---

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("menu_"))
async def menu_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    bot_status = await get_bot_status()
    if bot_status == "inactive" and data != "menu_profile":
        await callback.answer("ربات فعلاً غیرفعال است.", show_alert=True)
        return

    if data == "menu_profile":
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute("SELECT wallet, username, balance, linked_site FROM users WHERE user_id = ?", (user_id,))
            res = await cursor.fetchone()
            if not res:
                await callback.message.edit_text("خطا: کاربر یافت نشد.")
                return
            wallet, username, balance, linked_site = res

        linked_text = "متصل شده" if linked_site else "متصل نشده"
        text = (
            f"👤 اطلاعات پروفایل شما:\n\n"
            f"آیدی: `{user_id}`\n"
            f"نام کاربری: {username}\n"
            f"آدرس کیف پول: `{wallet}`\n"
            f"موجودی: {balance} تومان\n"
            f"وضعیت اتصال به سایت: {linked_text}"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("کپی آدرس کیف پول", callback_data="copy_wallet"),
            InlineKeyboardButton("کپی آیدی", callback_data="copy_userid")
        )
        kb.add(InlineKeyboardButton("بازگشت به منو اصلی", callback_data="back_to_main"))
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_topup":
        kb = topup_method_keyboard()
        await callback.message.edit_text("لطفا روش افزایش موجودی را انتخاب کنید:", reply_markup=kb)

    elif data == "menu_transfer":
        user_states[user_id] = {"state": "transfer_wait_wallet"}
        await callback.message.edit_text("آدرس کیف پول مقصد را وارد کنید:")

    elif data == "menu_support":
        user_states[user_id] = {"state": "support_wait_message"}
        await callback.message.edit_text("پیام خود را برای پشتیبانی ارسال کنید:")

    elif data == "menu_rules":
        rules_text = (
            "قوانین ربات:\n"
            "1. استفاده صحیح و منصفانه از ربات\n"
            "2. عدم ارسال پیام‌های مزاحم\n"
            "3. مسئولیت استفاده از کیف پول با خود شماست\n"
            "4. ... (بقیه قوانین)"
        )
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("خواندم", callback_data="rules_read"))
        await callback.message.edit_text(rules_text, reply_markup=kb)

    elif data == "rules_read":
        await callback.answer("ممنون که قوانین را مطالعه کردید.", show_alert=True)
        await callback.message.edit_text("بازگشت به منو اصلی.", reply_markup=main_menu_keyboard())

    elif data == "back_to_main":
        await callback.message.edit_text("بازگشت به منو اصلی.", reply_markup=main_menu_keyboard())

    elif data == "copy_wallet":
        wallet = await get_user_wallet(user_id)
        await callback.answer(f"آدرس کیف پول شما:\n{wallet}", show_alert=True)

    elif data == "copy_userid":
        await callback.answer(f"آیدی شما:\n{user_id}", show_alert=True)

    await callback.answer()

# --- هندلر انتخاب روش افزایش موجودی ---

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("topup_"))
async def topup_method_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if data == "topup_card_to_card":
        user_states[user_id] = {"state": "topup_wait_amount"}
        await callback.message.edit_text("لطفا مبلغ مورد نظر برای افزایش موجودی را به تومان وارد کنید:")

    elif data == "topup_gift_code":
        user_states[user_id] = {"state": "topup_wait_gift_code"}
        await callback.message.edit_text("کد هدیه خود را وارد کنید:")

    elif data == "topup_payment_gateway":
        await callback.answer("این روش فعلاً غیرفعال است.", show_alert=True)

    await callback.answer()

# --- هندلر دریافت مبلغ کارت به کارت ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "topup_wait_amount")
async def topup_receive_amount(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1000:
        await message.reply("لطفا مبلغ صحیح به تومان (بیش از 1000) وارد کنید.")
        return
    amount = int(text)
    user_states[user_id]["state"] = "topup_wait_receipt"
    user_states[user_id]["amount"] = amount
    await message.reply(f"لطفا عکس رسید کارت به کارت به مبلغ {amount} تومان را ارسال کنید.")

# --- هندلر دریافت عکس رسید ---

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def topup_receive_receipt(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {}).get("state")
    if state != "topup_wait_receipt":
        # پیام عکس نا مرتبط
        return

    amount = user_states[user_id]["amount"]
    photo = message.photo[-1]  # بهترین کیفیت
    file_id = photo.file_id

    # ذخیره درخواست در دیتابیس
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("INSERT INTO topup_requests (user_id, amount, receipt_file_id) VALUES (?, ?, ?)",
                         (user_id, amount, file_id))
        await db.commit()

    # اطلاع به مدیران
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id FROM admins")
        admins = await cursor.fetchall()

    text = (
        f"📥 درخواست افزایش موجودی جدید:\n"
        f"کاربر: {user_id}\n"
        f"مبلغ: {amount} تومان\n"
        f"وضعیت: در انتظار بررسی\n"
        f"برای تایید یا رد، از دکمه‌های زیر استفاده کنید."
    )

    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("تایید ✅", callback_data=f"admin_topup_accept_{user_id}"),
        InlineKeyboardButton("فیک ❌", callback_data=f"admin_topup_reject_{user_id}"),
        InlineKeyboardButton("پیام به کاربر 💬", callback_data=f"admin_topup_message_{user_id}")
    )

    for admin in admins:
        try:
            await bot.send_photo(admin[0], file_id, caption=text, reply_markup=kb)
        except Exception as e:
            logging.warning(f"ارسال به ادمین {admin[0]} موفق نبود: {e}")

    user_states.pop(user_id, None)
    await message.reply("درخواست شما ثبت شد و در انتظار تایید مدیر است.")

# --- هندلر دکمه های مدیریت درخواست افزایش موجودی ---

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_topup_"))
async def admin_topup_handler(callback: types.CallbackQuery):
    data = callback.data
    admin_id = callback.from_user.id

    if not await is_admin(admin_id):
        await callback.answer("شما مدیر نیستید.", show_alert=True)
        return

    parts = data.split("_")
    action = parts[2]  # accept, reject, message
    target_user_id = int(parts[3])

    if action == "accept":
        # تایید افزایش موجودی
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute(
                "SELECT amount, status FROM topup_requests WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
                (target_user_id,))
            res = await cursor.fetchone()
            if not res:
                await callback.answer("درخواستی برای این کاربر یافت نشد.", show_alert=True)
                return
            amount, status = res
            if status != "pending":
                await callback.answer("درخواست قبلاً بررسی شده است.", show_alert=True)
                return

            await update_user_balance(target_user_id, amount)
            await db.execute(
                "UPDATE topup_requests SET status = 'accepted' WHERE user_id = ? AND status = 'pending'",
                (target_user_id,))
            await db.commit()

        await callback.answer("درخواست تایید شد.", show_alert=True)
        try:
            await bot.send_message(target_user_id, f"درخواست افزایش موجودی شما به مبلغ {amount} تومان تایید شد و موجودی شما افزایش یافت.")
        except:
            pass
        await callback.message.edit_reply_markup(reply_markup=None)

    elif action == "reject":
        # رد درخواست
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute(
                "SELECT amount FROM topup_requests WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
                (target_user_id,))
            res = await cursor.fetchone()
            if not res:
                await callback.answer("درخواستی برای این کاربر یافت نشد.", show_alert=True)
                return
            amount = res[0]

            await db.execute(
                "UPDATE topup_requests SET status = 'rejected' WHERE user_id = ? AND status = 'pending'",
                (target_user_id,))
            await db.commit()

        await callback.answer("درخواست رد شد.", show_alert=True)
        try:
            await bot.send_message(target_user_id, f"متاسفانه درخواست افزایش موجودی شما به مبلغ {amount} تومان رد شد.")
        except:
            pass
        await callback.message.edit_reply_markup(reply_markup=None)

    elif action == "message":
        # ارسال پیام به کاربر (از طرف مدیر)
        user_states[admin_id] = {"state": "admin_message_to_user", "target_user_id": target_user_id}
        await callback.answer()
        await callback.message.answer(f"پیام خود را برای کاربر {target_user_id} ارسال کنید:")

# --- هندلر پیام مدیر برای کاربر ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "admin_message_to_user")
async def admin_send_message_to_user(message: types.Message):
    admin_id = message.from_user.id
    state_data = user_states.get(admin_id)
    if not state_data:
        return
    target_user_id = state_data.get("target_user_id")
    if not target_user_id:
        return
    text = message.text or ""
    if not text.strip():
        await message.reply("پیام نباید خالی باشد.")
        return

    try:
        await bot.send_message(target_user_id, f"📩 پیام از مدیر:\n\n{text}")
        await message.reply("پیام با موفقیت ارسال شد.")
    except Exception as e:
        await message.reply(f"ارسال پیام با خطا مواجه شد: {e}")

    user_states.pop(admin_id, None)

# --- هندلر انتقال موجودی ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "transfer_wait_wallet")
async def transfer_receive_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()
    if not wallet.startswith("wallet_"):
        await message.reply("آدرس کیف پول معتبر نیست. مجددا وارد کنید.")
        return
    user_states[user_id]["wallet_dest"] = wallet
    user_states[user_id]["state"] = "transfer_wait_amount"
    await message.reply("مبلغ انتقال را به تومان وارد کنید:")

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "transfer_wait_amount")
async def transfer_receive_amount(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.reply("مبلغ معتبر وارد کنید.")
        return
    amount = int(text)
    wallet_dest = user_states[user_id].get("wallet_dest")
    balance = await get_user_balance(user_id)
    if amount > balance:
        await message.reply("موجودی شما کافی نیست.")
        return

    # کم کردن مبلغ از فرستنده و اضافه کردن به گیرنده (بر اساس آدرس کیف پول)
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id, balance FROM users WHERE wallet = ?", (wallet_dest,))
        dest_res = await cursor.fetchone()
        if not dest_res:
            await message.reply("آدرس کیف پول مقصد یافت نشد.")
            return
        dest_user_id, dest_balance = dest_res
        # تراکنش کاهش و افزایش
        await update_user_balance_set(user_id, balance - amount)
        await update_user_balance(dest_user_id, amount)
        # ذخیره تراکنش
        await db.execute(
            "INSERT INTO transactions (from_user, to_wallet, amount, type) VALUES (?, ?, ?, ?)",
            (user_id, wallet_dest, amount, "transfer")
        )
        await db.commit()

    user_states.pop(user_id, None)
    await message.reply(f"انتقال با موفقیت انجام شد.\nمبلغ {amount} تومان به {wallet_dest} ارسال شد.")

# --- هندلر پیام پشتیبانی ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "support_wait_message")
async def support_receive_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text or ""
    if not text.strip():
        await message.reply("پیام نمی‌تواند خالی باشد.")
        return

    # ارسال پیام به همه مدیران
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id FROM admins")
        admins = await cursor.fetchall()

    for admin in admins:
        try:
            await bot.send_message(admin[0], f"📞 پیام از کاربر {user_id}:\n\n{text}")
        except Exception as e:
            logging.warning(f"ارسال پیام پشتیبانی به ادمین {admin[0]} موفق نبود: {e}")

    user_states.pop(user_id, None)
    await message.reply("پیام شما به پشتیبانی ارسال شد. به زودی پاسخ داده خواهد شد.")

# --- هندلر ثبت ادمین جدید (فقط برای مدیر اصلی) ---

@dp.callback_query_handler(lambda c: c.data == "admin_add_new_admin")
async def admin_add_new_admin_handler(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    if not await is_super_admin(admin_id):
        await callback.answer("شما مدیر اصلی نیستید.", show_alert=True)
        return
    user_states[admin_id] = {"state": "add_new_admin_wait_id"}
    await callback.message.edit_text("لطفا آیدی عددی کاربر جدید برای ثبت به عنوان ادمین را وارد کنید:")

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "add_new_admin_wait_id")
async def add_new_admin_receive_id(message: types.Message):
    admin_id = message.from_user.id
    text = message.text.strip()
    if not text.isdigit():
        await message.reply("آیدی معتبر وارد کنید.")
        return
    new_admin_id = int(text)
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id FROM admins WHERE user_id = ?", (new_admin_id,))
        res = await cursor.fetchone()
        if res:
            await message.reply("این کاربر قبلاً ادمین ثبت شده است.")
            return
        await db.execute("INSERT INTO admins (user_id, is_super) VALUES (?, 0)", (new_admin_id,))
        await db.commit()

    user_states.pop(admin_id, None)
    await message.reply(f"کاربر {new_admin_id} به عنوان ادمین ثبت شد.")

# --- هندلر منوی ادمین ---

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.reply("شما مدیر نیستید.")
        return
    is_super = await is_super_admin(user_id)
    kb = admin_main_menu_keyboard(is_super)
    await message.answer("منوی مدیریت:", reply_markup=kb)

# --- هندلر دکمه های منوی ادمین ---

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_"))
async def admin_menu_handler(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    data = callback.data

    if not await is_admin(admin_id):
        await callback.answer("شما مدیر نیستید.", show_alert=True)
        return

    if data == "admin_increase_balance":
        user_states[admin_id] = {"state": "admin_increase_balance_wait_user"}
        await callback.message.edit_text("آیدی عددی کاربر برای افزایش موجودی را وارد کنید:")

    elif data == "admin_create_gift_code":
        user_states[admin_id] = {"state": "admin_create_gift_code_wait_code"}
        await callback.message.edit_text("کد هدیه جدید را وارد کنید:")

    elif data == "admin_create_discount_code":
        user_states[admin_id] = {"state": "admin_create_discount_code_wait_code"}
        await callback.message.edit_text("کد تخفیف جدید را وارد کنید:")

    elif data == "admin_financial_report":
        # گزارش مالی کلی - خلاصه
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute("SELECT COUNT(*), SUM(amount) FROM topup_requests WHERE status = 'accepted'")
            count, total_amount = await cursor.fetchone()
        total_amount = total_amount or 0
        await callback.message.edit_text(f"تعداد درخواست‌های تایید شده: {count}\nمجموع مبلغ افزایش موجودی: {total_amount} تومان")

    elif data == "admin_toggle_bot":
        current_status = await get_bot_status()
        new_status = "inactive" if current_status == "active" else "active"
        await set_bot_status(new_status)
        await callback.message.edit_text(f"وضعیت ربات به '{new_status}' تغییر کرد.")

# --- هندلر مرحله‌های افزایش موجودی توسط مدیر ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "admin_increase_balance_wait_user")
async def admin_increase_balance_wait_user(message: types.Message):
    admin_id = message.from_user.id
    text = message.text.strip()
    if not text.isdigit():
        await message.reply("آیدی عددی معتبر وارد کنید.")
        return
    target_user_id = int(text)
    user_states[admin_id]["target_user_id"] = target_user_id
    user_states[admin_id]["state"] = "admin_increase_balance_wait_amount"
    await message.reply(f"مبلغ افزایش موجودی برای کاربر {target_user_id} را وارد کنید:")

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "admin_increase_balance_wait_amount")
async def admin_increase_balance_wait_amount(message: types.Message):
    admin_id = message.from_user.id
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.reply("مبلغ معتبر وارد کنید.")
        return
    amount = int(text)
    target_user_id = user_states[admin_id]["target_user_id"]

    # افزایش موجودی
    await update_user_balance(target_user_id, amount)
    user_states.pop(admin_id, None)
    await message.reply(f"موجودی کاربر {target_user_id} به مقدار {amount} تومان افزایش یافت.")

# --- هندلر ایجاد کد هدیه ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "admin_create_gift_code_wait_code")
async def admin_create_gift_code_wait_code(message: types.Message):
    admin_id = message.from_user.id
    code = message.text.strip()
    if len(code) < 3:
        await message.reply("کد هدیه باید حداقل 3 کاراکتر باشد.")
        return
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT code FROM gift_codes WHERE code = ?", (code,))
        exists = await cursor.fetchone()
        if exists:
            await message.reply("این کد قبلاً ثبت شده است.")
            return
        await db.execute("INSERT INTO gift_codes (code, used) VALUES (?, 0)", (code,))
        await db.commit()
    user_states.pop(admin_id, None)
    await message.reply(f"کد هدیه '{code}' ثبت شد.")

# --- هندلر استفاده از کد هدیه توسط کاربر ---

@dp.message_handler(commands=["usegift"])
async def cmd_use_gift(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()
    if not args:
        await message.reply("برای استفاده از کد هدیه، بعد از دستور /usegift کد را وارد کنید.\nمثال: /usegift CODE123")
        return
    code = args.strip()
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT used FROM gift_codes WHERE code = ?", (code,))
        res = await cursor.fetchone()
        if not res:
            await message.reply("کد هدیه یافت نشد.")
            return
        if res[0]:
            await message.reply("این کد هدیه قبلاً استفاده شده است.")
            return
        # افزایش موجودی (مثلاً 10000 تومان برای نمونه)
        await update_user_balance(user_id, 10000)
        await db.execute("UPDATE gift_codes SET used = 1 WHERE code = ?", (code,))
        await db.commit()
    await message.reply(f"کد هدیه '{code}' با موفقیت استفاده شد و 10000 تومان به موجودی شما اضافه گردید.")

# --- هندلر ایجاد کد تخفیف توسط مدیر ---

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "admin_create_discount_code_wait_code")
async def admin_create_discount_code_wait_code(message: types.Message):
    admin_id = message.from_user.id
    code = message.text.strip()
    if len(code) < 3:
        await message.reply("کد تخفیف باید حداقل 3 کاراکتر باشد.")
        return
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT code FROM discount_codes WHERE code = ?", (code,))
        exists = await cursor.fetchone()
        if exists:
            await message.reply("این کد قبلاً ثبت شده است.")
            return
        await db.execute("INSERT INTO discount_codes (code, used) VALUES (?, 0)", (code,))
        await db.commit()
    user_states.pop(admin_id, None)
    await message.reply(f"کد تخفیف '{code}' ثبت شد.")

# --- دستورات شروع و استارت ربات ---

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    wallet = await get_or_create_wallet(user_id)
    # ثبت کاربر در دیتابیس اگر جدید باشد
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if not res:
            await db.execute("INSERT INTO users (user_id, username, full_name, wallet, balance) VALUES (?, ?, ?, ?, ?)",
                             (user_id, username, full_name, wallet, 0))
            await db.commit()

    await message.answer(
        f"سلام {full_name}!\n"
        f"به ربات کیف پول خوش آمدید.\n"
        f"از منوی زیر یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=main_menu_keyboard()
    )

# --- توابع کمکی ---

async def get_or_create_wallet(user_id: int) -> str:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if res and res[0]:
            return res[0]
        # ایجاد آدرس کیف پول جدید به صورت wallet_<user_id>
        wallet = f"wallet_{user_id}"
        await db.execute("UPDATE users SET wallet = ? WHERE user_id = ?", (wallet, user_id))
        await db.commit()
        return wallet

async def get_user_wallet(user_id: int) -> str:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if res:
            return res[0]
        return ""

async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if res:
            return res[0]
        return 0

async def update_user_balance(user_id: int, amount: int):
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if not res:
            return
        current_balance = res[0]
        new_balance = current_balance + amount
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()

async def update_user_balance_set(user_id: int, new_balance: int):
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return bool(res)

async def is_super_admin(user_id: int) -> bool:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_super FROM admins WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return bool(res and res[0])

async def get_bot_status() -> str:
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'bot_status'")
        res = await cursor.fetchone()
        if res:
            return res[0]
        return "active"

async def set_bot_status(status: str):
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (status,))
        await db.commit()

# --- کلیدهای کیبورد ---

def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("پروفایل", callback_data="profile"),
        InlineKeyboardButton("افزایش موجودی", callback_data="increase_balance"),
        InlineKeyboardButton("کارت به کارت", callback_data="topup_card_to_card"),
        InlineKeyboardButton("ارتباط با پشتیبانی", callback_data="support_contact")
    )
    return keyboard

def admin_main_menu_keyboard(is_super: bool):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("افزایش موجودی دستی", callback_data="admin_increase_balance"),
        InlineKeyboardButton("ایجاد کد هدیه", callback_data="admin_create_gift_code"),
        InlineKeyboardButton("ایجاد کد تخفیف", callback_data="admin_create_discount_code"),
        InlineKeyboardButton("گزارش مالی", callback_data="admin_financial_report"),
        InlineKeyboardButton("تغییر وضعیت ربات", callback_data="admin_toggle_bot"),
    )
    if is_super:
        keyboard.add(InlineKeyboardButton("ثبت ادمین جدید", callback_data="admin_add_new_admin"))
    return keyboard

# --- راه‌اندازی دیتابیس ---

async def setup_database():
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            wallet TEXT UNIQUE,
            balance INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            is_super INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS topup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            used INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS discount_codes (
            code TEXT PRIMARY KEY,
            used INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER,
            to_wallet TEXT,
            amount INTEGER,
            type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await db.commit()

# --- شروع اصلی ---

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from aiogram import executor

    import asyncio
    asyncio.run(setup_database())
    executor.start_polling(dp, skip_updates=True)




