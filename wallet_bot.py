import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import aiosqlite
from datetime import datetime

API_TOKEN = os.getenv("API_TOKEN")

DATABASE = 'wallet_bot.db'
MAIN_ADMIN_CODE = "123456"  # کد ثابت برای ثبت مدیر اصلی
BANK_CARD_NUMBER = "5022-2915-3068-9296"  # شماره کارت برای کارت به کارت

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# --- حالت‌ها ---

class TopUpStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


class GiftCodeStates(StatesGroup):
    waiting_for_code = State()


class DiscountCodeStates(StatesGroup):
    waiting_for_code = State()


class TransferStates(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_amount = State()


class SupportStates(StatesGroup):
    waiting_for_message = State()


class AdminMessageStates(StatesGroup):
    waiting_for_reply = State()


class RegisterAdminStates(StatesGroup):
    waiting_for_code = State()


# --- دیتابیس و توابع کمکی ---

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                wallet_address TEXT UNIQUE,
                linked_site INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                photo_file_id TEXT,
                status TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                amount INTEGER,
                used INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                percent INTEGER,
                active INTEGER DEFAULT 1
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                created_at TEXT,
                replied INTEGER DEFAULT 0,
                reply TEXT
            )
        ''')
        await db.commit()


def generate_wallet_address(user_id: int) -> str:
    return f"wallet_{user_id}"


async def get_user_info(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT username, wallet_address, balance, linked_site FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()


async def get_user_balance(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_user_balance(user_id, amount_change):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_change, user_id))
        await db.commit()


async def is_admin(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row and row[0])


async def set_admin(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_pending_receipts():
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT id, user_id, amount, photo_file_id, status, created_at FROM receipts WHERE status = 'pending'")
        return await cursor.fetchall()


async def update_receipt_status(receipt_id, status):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE receipts SET status = ? WHERE id = ?", (status, receipt_id))
        await db.commit()


async def get_username(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def save_support_message(user_id, message_text):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT INTO support_messages (user_id, message, created_at) VALUES (?, ?, ?)",
            (user_id, message_text, datetime.now().isoformat())
        )
        await db.commit()


async def get_unreplied_support_messages():
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT id, user_id, message FROM support_messages WHERE replied = 0")
        return await cursor.fetchall()


async def reply_support_message(message_id, reply_text):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE support_messages SET reply = ?, replied = 1 WHERE id = ?", (reply_text, message_id))
        await db.commit()


# --- کیبوردها ---

def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("شارژ حساب (کارت به کارت)", callback_data="topup"),
        InlineKeyboardButton("انتقال موجودی", callback_data="transfer"),
        InlineKeyboardButton("کد هدیه", callback_data="giftcode"),
        InlineKeyboardButton("کد تخفیف", callback_data="discountcode"),
        InlineKeyboardButton("پروفایل", callback_data="profile"),
        InlineKeyboardButton("ارتباط با پشتیبانی", callback_data="support"),
    )
    return keyboard


def admin_panel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("مشاهده درخواست‌های شارژ", callback_data="admin_topups"),
        InlineKeyboardButton("ایجاد کد هدیه", callback_data="admin_create_giftcode"),
        InlineKeyboardButton("ایجاد کد تخفیف", callback_data="admin_create_discount"),
        InlineKeyboardButton("مدیریت مدیران", callback_data="admin_manage_admins"),
        InlineKeyboardButton("گزارش مالی", callback_data="admin_reports"),
        InlineKeyboardButton("خروج از پنل", callback_data="admin_logout"),
    )
    return keyboard


def receipt_admin_keyboard(receipt_id):
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("تأیید", callback_data=f"receipt_confirm_{receipt_id}"),
        InlineKeyboardButton("فیک", callback_data=f"receipt_fake_{receipt_id}"),
        InlineKeyboardButton("پیام به کاربر", callback_data=f"receipt_msg_{receipt_id}"),
    )
    return keyboard


def support_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("ارتباط با پشتیبانی", callback_data="support")
    )
    return keyboard


# --- هندلرها ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, balance, wallet_address, linked_site) VALUES (?, ?, 0, ?, 0)",
            (user_id, username, generate_wallet_address(user_id)),
        )
        await db.commit()

    # بررسی آیا ادمین هست
    if await is_admin(user_id):
        text = f"سلام مدیر عزیز {username}!\nبه پنل ربات خوش آمدید."
        await message.answer(text, reply_markup=admin_panel_keyboard())
    else:
        await message.answer(
            f"سلام {username}!\nبه ربات کیف پول خوش آمدید.",
            reply_markup=main_menu_keyboard()
        )


@dp.message_handler(commands=['registeradmin'])
async def cmd_register_admin(message: types.Message):
    await message.answer("لطفا کد ثبت مدیر را وارد کنید:")
    await RegisterAdminStates.waiting_for_code.set()


@dp.message_handler(state=RegisterAdminStates.waiting_for_code)
async def process_register_admin_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code == MAIN_ADMIN_CODE:
        await set_admin(message.from_user.id)
        await message.answer("شما به عنوان مدیر ثبت شدید. لطفا /start را بزنید.")
    else:
        await message.answer("کد اشتباه است.")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "profile")
async def show_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_info = await get_user_info(user_id)
    if not user_info:
        await callback_query.answer("شما در سیستم ثبت نشده‌اید.")
        return

    username, wallet_address, balance, linked_site = user_info
    linked_status = "لینک نشده" if linked_site == 0 else "لینک شده"

    text = (
        f"👤 نام کاربری: @{username}\n"
        f"🆔 آیدی: {user_id}\n"
        f"💼 آدرس کیف پول: `{wallet_address}`\n"
        f"💰 موجودی: {balance} تومان\n"
        f"🔗 وضعیت اتصال به سایت: {linked_status}"
    )
    await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "topup")
async def process_topup(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.send_message(user_id,
                           f"برای شارژ موجودی، مبلغ را وارد کنید (تومان):\n"
                           f"شماره کارت برای کارت به کارت:\n`{BANK_CARD_NUMBER}`\n"
                           f"به محض واریز رسید عکس را ارسال کنید.")
    await TopUpStates.waiting_for_amount.set()
    await callback_query.answer()


@dp.message_handler(state=TopUpStates.waiting_for_amount)
async def topup_amount_entered(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("مبلغ باید عددی مثبت باشد.")
            return
        await state.update_data(amount=amount)
        await message.answer("لطفا عکس رسید کارت به کارت را ارسال کنید.")
        await TopUpStates.waiting_for_receipt.set()
    except ValueError:
        await message.answer("لطفا فقط عدد وارد کنید.")


@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=TopUpStates.waiting_for_receipt)
async def topup_receipt_received(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    amount = data.get("amount")
    photo = message.photo[-1]
    file_id = photo.file_id

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT INTO receipts (user_id, amount, photo_file_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, file_id, "pending", datetime.now().isoformat())
        )
        await db.commit()

    await message.answer("رسید شما با موفقیت ارسال شد. پس از بررسی توسط مدیریت، موجودی شما افزایش خواهد یافت.")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "giftcode")
async def giftcode_handler(callback_query: types.CallbackQuery):
    await callback_query.message.answer("برای استفاده از کد هدیه، لطفا کد را ارسال کنید:")
    await GiftCodeStates.waiting_for_code.set()
    await callback_query.answer()


@dp.message_handler(state=GiftCodeStates.waiting_for_code)
async def giftcode_received(message: types.Message, state: FSMContext):
    code = message.text.strip()
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT amount, used FROM gift_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if not row:
            await message.answer("کد هدیه معتبر نیست.")
            await state.finish()
            return
        amount, used = row
        if used:
            await message.answer("این کد هدیه قبلا استفاده شده است.")
            await state.finish()
            return
        # اعمال مقدار به موجودی کاربر
        await update_user_balance(message.from_user.id, amount)
        # علامت استفاده شده
        await db.execute("UPDATE gift_codes SET used = 1 WHERE code = ?", (code,))
        await db.commit()

    await message.answer(f"کد هدیه با موفقیت اعمال شد. مبلغ {amount} تومان به موجودی شما اضافه گردید.")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "discountcode")
async def discountcode_handler(callback_query: types.CallbackQuery):
    await callback_query.message.answer("برای استفاده از کد تخفیف، لطفا کد را ارسال کنید:")
    await DiscountCodeStates.waiting_for_code.set()
    await callback_query.answer()


@dp.message_handler(state=DiscountCodeStates.waiting_for_code)
async def discountcode_received(message: types.Message, state: FSMContext):
    code = message.text.strip()
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT percent, active FROM discount_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if not row:
            await message.answer("کد تخفیف معتبر نیست.")
            await state.finish()
            return
        percent, active = row
        if not active:
            await message.answer("این کد تخفیف غیر فعال است.")
            await state.finish()
            return

    await message.answer(f"کد تخفیف معتبر است و {percent}% تخفیف برای شما اعمال می‌شود (در مراحل بعد).")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "transfer")
async def transfer_start(callback_query: types.CallbackQuery):
    await callback_query.message.answer("لطفا آدرس کیف پول مقصد را وارد کنید:")
    await TransferStates.waiting_for_wallet.set()
    await callback_query.answer()


@dp.message_handler(state=TransferStates.waiting_for_wallet)
async def transfer_wallet_entered(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    # در اینجا می‌توانید اعتبارسنجی آدرس کیف پول اضافه کنید
    await state.update_data(wallet=wallet)
    await message.answer("مبلغ انتقال را وارد کنید (تومان):")
    await TransferStates.waiting_for_amount.set()


@dp.message_handler(state=TransferStates.waiting_for_amount)
async def transfer_amount_entered(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("مبلغ باید عددی مثبت باشد.")
            return
        data = await state.get_data()
        wallet = data.get("wallet")
        user_id = message.from_user.id
        balance = await get_user_balance(user_id)
        if amount > balance:
            await message.answer("موجودی کافی نیست.")
            return
        # کسر مبلغ از موجودی کاربر
        await update_user_balance(user_id, -amount)
        # در اینجا ذخیره تراکنش انتقال (در دیتابیس یا لاگ) می‌توانید انجام دهید
        await message.answer(f"مبلغ {amount} تومان به آدرس کیف پول {wallet} منتقل شد.")
        await state.finish()
    except ValueError:
        await message.answer("لطفا فقط عدد وارد کنید.")


@dp.callback_query_handler(lambda c: c.data == "support")
async def support_start(callback_query: types.CallbackQuery):
    await callback_query.message.answer("لطفا پیام خود را برای پشتیبانی ارسال کنید:")
    await SupportStates.waiting_for_message.set()
    await callback_query.answer()


@dp.message_handler(state=SupportStates.waiting_for_message)
async def support_message_received(message: types.Message, state: FSMContext):
    await save_support_message(message.from_user.id, message.text)
    await message.answer("پیام شما به پشتیبانی ارسال شد. در اسرع وقت پاسخ داده خواهد شد.")
    await state.finish()


# --- مدیریت درخواست‌های شارژ ---

@dp.callback_query_handler(lambda c: c.data == "admin_topups")
async def admin_view_topups(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return

    receipts = await get_pending_receipts()
    if not receipts:
        await callback_query.message.answer("درخواست شارژ جدیدی وجود ندارد.")
        return

    for receipt in receipts:
        rid, uid, amount, photo_file_id, status, created_at = receipt
        username = await get_username(uid) or "کاربر ناشناس"
        text = (
            f"درخواست شارژ #{rid}\n"
            f"کاربر: @{username} (ID: {uid})\n"
            f"مبلغ: {amount} تومان\n"
            f"وضعیت: {status}\n"
            f"زمان ارسال: {created_at}"
        )
        await callback_query.message.answer_photo(photo_file_id, caption=text, reply_markup=receipt_admin_keyboard(rid))

    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("receipt_confirm_"))
async def admin_confirm_receipt(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    receipt_id = int(callback_query.data[len("receipt_confirm_"):])
    # بروزرسانی وضعیت رسید به تایید شده
    await update_receipt_status(receipt_id, "confirmed")

    # افزایش موجودی کاربر مربوطه
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id, amount FROM receipts WHERE id = ?", (receipt_id,))
        row = await cursor.fetchone()
        if row:
            uid, amount = row
            await update_user_balance(uid, amount)
    await callback_query.answer("رسید تایید شد و موجودی کاربر افزایش یافت.")
    await callback_query.message.delete()


@dp.callback_query_handler(lambda c: c.data.startswith("receipt_fake_"))
async def admin_fake_receipt(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    receipt_id = int(callback_query.data[len("receipt_fake_"):])
    await update_receipt_status(receipt_id, "fake")
    await callback_query.answer("رسید به عنوان فیک علامت گذاری شد.")
    await callback_query.message.delete()


@dp.callback_query_handler(lambda c: c.data.startswith("receipt_msg_"))
async def admin_message_to_user(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    receipt_id = int(callback_query.data[len("receipt_msg_"):])
    await state.update_data(receipt_id=receipt_id)
    await callback_query.message.answer("پیام خود به کاربر را وارد کنید:")
    await AdminMessageStates.waiting_for_reply.set()
    await callback_query.answer()


@dp.message_handler(state=AdminMessageStates.waiting_for_reply)
async def admin_send_message_to_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("receipt_id")
    if not receipt_id:
        await message.answer("خطا در پیدا کردن رسید.")
        await state.finish()
        return

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM receipts WHERE id = ?", (receipt_id,))
        row = await cursor.fetchone()
        if not row:
            await message.answer("رسید یافت نشد.")
            await state.finish()
            return
        user_id = row[0]

    # ارسال پیام به کاربر
    await bot.send_message(user_id, f"پیام مدیریت درباره رسید شما:\n\n{message.text}")
    await message.answer("پیام ارسال شد.")
    await state.finish()


# --- مدیریت پنل ---

@dp.callback_query_handler(lambda c: c.data == "admin_create_giftcode")
async def admin_create_giftcode_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    await callback_query.message.answer("کد هدیه جدید را به صورت `کد مبلغ` وارد کنید (مثال: ABC123 10000):")
    await GiftCodeStates.waiting_for_code.set()
    await callback_query.answer()


@dp.message_handler(state=GiftCodeStates.waiting_for_code)
async def admin_create_giftcode(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("دسترسی غیرمجاز!")
        await state.finish()
        return
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("فرمت اشتباه است. لطفا مانند مثال کد و مبلغ را وارد کنید.")
        return
    code, amount_str = parts
    try:
        amount = int(amount_str)
        if amount <= 0:
            await message.answer("مبلغ باید مثبت باشد.")
            return
    except:
        await message.answer("مبلغ باید عدد صحیح باشد.")
        return

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute("INSERT INTO gift_codes (code, amount) VALUES (?, ?)", (code, amount))
            await db.commit()
            await message.answer(f"کد هدیه {code} با مبلغ {amount} تومان ساخته شد.")
        except:
            await message.answer("این کد قبلا وجود دارد.")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "admin_create_discount")
async def admin_create_discount_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    await callback_query.message.answer("کد تخفیف جدید را به صورت `کد درصد` وارد کنید (مثال: DISC10 10):")
    await DiscountCodeStates.waiting_for_code.set()
    await callback_query.answer()


@dp.message_handler(state=DiscountCodeStates.waiting_for_code)
async def admin_create_discount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("دسترسی غیرمجاز!")
        await state.finish()
        return
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("فرمت اشتباه است. لطفا مانند مثال کد و درصد را وارد کنید.")
        return
    code, percent_str = parts
    try:
        percent = int(percent_str)
        if percent <= 0 or percent > 100:
            await message.answer("درصد باید بین 1 تا 100 باشد.")
            return
    except:
        await message.answer("درصد باید عدد صحیح باشد.")
        return

    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute("INSERT INTO discount_codes (code, percent) VALUES (?, ?)", (code, percent))
            await db.commit()
            await message.answer(f"کد تخفیف {code} با درصد {percent}% ساخته شد.")
        except:
            await message.answer("این کد قبلا وجود دارد.")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "admin_manage_admins")
async def admin_manage_admins(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    await callback_query.message.answer(
        "برای ثبت مدیر جدید دستور /registeradmin را بفرستید."
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "admin_reports")
async def admin_reports(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await is_admin(user_id):
        await callback_query.answer("دسترسی غیرمجاز!")
        return
    # گزارش ساده: مجموع تراکنش‌ها یا تعداد کاربران و موجودی کل
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        users_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(balance) FROM users")
        total_balance = (await cursor.fetchone())[0] or 0
        cursor = await db.execute("SELECT COUNT(*) FROM receipts WHERE status = 'pending'")
        pending_receipts = (await cursor.fetchone())[0]

    report_text = (
        f"📊 گزارش مالی\n"
        f"تعداد کاربران: {users_count}\n"
        f"مجموع موجودی کاربران: {total_balance} تومان\n"
        f"درخواست‌های شارژ در انتظار: {pending_receipts}"
    )
    await callback_query.message.answer(report_text)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "admin_logout")
async def admin_logout(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    # اگر نیاز بود می‌توان دسترسی را برداشت اما اینجا فقط پیام می‌دهیم
    await callback_query.message.answer("از پنل مدیریت خارج شدید.\nبرای ورود مجدد /start بزنید.")
    await callback_query.answer()


# --- اجرای اولیه ---

async def on_startup(dp):
    await init_db()
    print("Bot started and DB initialized.")


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup)
