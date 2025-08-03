import logging
import aiosqlite
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import os

# ====== تنظیمات ======
TOKEN = os.getenv("API_TOKEN")
ADMIN_CODE = "123456"  # کد ثبت مدیر اصلی

DATABASE = "wallet_bot.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# ====== کلاس‌های حالت (FSM) ======
class RegisterAdminStates(StatesGroup):
    waiting_for_admin_code = State()


class TopUpStates(StatesGroup):
    waiting_for_topup_method = State()
    waiting_for_card_receipt_photo = State()
    waiting_for_topup_amount = State()
    waiting_for_giftcode = State()
    waiting_for_discountcode = State()


class TransferStates(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_amount = State()


class SupportStates(StatesGroup):
    waiting_for_message = State()


class AdminMessageStates(StatesGroup):
    waiting_for_reply = State()


# ====== کمک‌کننده‌های دیتابیس ======
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        # جدول کاربران
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0
            )
        """)
        # جدول رسیدهای کارت به کارت
        await db.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                photo_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول کد هدیه
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                amount INTEGER
            )
        """)
        # جدول کد تخفیف
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                percent INTEGER
            )
        """)
        # جدول پیام‌های پشتیبانی
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row and row[0] == 1:
            return True
        return False


async def is_main_admin_exists() -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        row = await cursor.fetchone()
        return row[0] > 0


async def register_main_admin(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, full_name, is_admin) VALUES (?, ?, ?, 1)
        """, (user_id, username, full_name))
        await db.commit()


async def add_user_if_not_exists(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                             (user_id, username, full_name))
            await db.commit()


async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_user_balance(user_id: int, amount_change: int):
    async with aiosqlite.connect(DATABASE) as db:
        # ابتدا موجودی فعلی را بگیر
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return False
        new_balance = row[0] + amount_change
        if new_balance < 0:
            return False
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()
        return True


async def save_receipt(user_id: int, amount: int, photo_file_id: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT INTO receipts (user_id, amount, photo_file_id) VALUES (?, ?, ?)
        """, (user_id, amount, photo_file_id))
        await db.commit()


async def save_support_message(user_id: int, message: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT INTO support_messages (user_id, message) VALUES (?, ?)", (user_id, message))
        await db.commit()


async def check_gift_code(code: str) -> int:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT amount FROM gift_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        return 0


async def delete_gift_code(code: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM gift_codes WHERE code = ?", (code,))
        await db.commit()


async def check_discount_code(code: str) -> int:
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT percent FROM discount_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        return 0


# ====== کیبوردها ======

def main_menu_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("پروفایل")],
        [KeyboardButton("افزایش موجودی")],
        [KeyboardButton("انتقال موجودی")],
        [KeyboardButton("قوانین")],
        [KeyboardButton("ارتباط با پشتیبانی")]
    ]
    if is_admin_user:
        buttons.append([KeyboardButton("پنل مدیریت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def topup_method_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("کارت به کارت", callback_data="topup_card"),
        InlineKeyboardButton("کد هدیه", callback_data="topup_giftcode"),
        InlineKeyboardButton("درگاه پرداخت (غیرفعال)", callback_data="topup_gateway_disabled"),
        InlineKeyboardButton("بازگشت", callback_data="topup_back"),
    )
    return kb


def cancel_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("انصراف"))
    return kb


def back_inline_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("بازگشت", callback_data="back"))
    return kb


# ====== هندلرها ======

# ورود / استارت
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""
    # چک ثبت ادمین اصلی
    if not await is_main_admin_exists():
        # اگر ادمین اصلی ثبت نشده، فقط اجازه ثبت آن را بده
        await message.answer(
            "ربات هنوز فعال نشده است.\n"
            "برای فعالسازی، کد مدیر اصلی را ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        await RegisterAdminStates.waiting_for_admin_code.set()
        return

    # ثبت یا بروزرسانی کاربر عادی
    await add_user_if_not_exists(user_id, username, full_name)

    is_admin_user = await is_admin(user_id)
    await message.answer(
        f"سلام {full_name}!\nبه ربات کیف پول خوش آمدید.",
        reply_markup=main_menu_keyboard(is_admin_user)
    )


# ثبت مدیر اصلی
@dp.message_handler(state=RegisterAdminStates.waiting_for_admin_code)
async def register_admin_code_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("ثبت مدیر اصلی لغو شد.\nبرای شروع مجدد /start را بزنید.")
        await state.finish()
        return

    if message.text == ADMIN_CODE:
        user_id = message.from_user.id
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await register_main_admin(user_id, username, full_name)
        await message.answer("مدیر اصلی با موفقیت ثبت شد. اکنون می‌توانید از ربات استفاده کنید.")
        await state.finish()
    else:
        await message.answer("کد اشتباه است. لطفا دوباره وارد کنید یا 'انصراف' بزنید.")


# --- منوی پروفایل ---
@dp.message_handler(lambda m: m.text == "پروفایل")
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    is_admin_user = await is_admin(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT balance, username, full_name FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await message.answer("شما در سیستم ثبت نشده‌اید.")
            return
        balance, username, full_name = row
        # وضعیت اتصال سایت فعلا 'غیر لینک شده'
        status_site = "غیر لینک شده"

    text = (
        f"👤 مشخصات شما:\n"
        f"نام کامل: {full_name}\n"
        f"نام کاربری: @{username if username else 'ندارد'}\n"
        f"موجودی: {balance} تومان\n"
        f"وضعیت اتصال به سایت: {status_site}"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(is_admin_user))


# --- منوی قوانین ---
@dp.message_handler(lambda m: m.text == "قوانین")
async def cmd_rules(message: types.Message):
    rules_text = (
        "📜 قوانین استفاده از ربات کیف پول:\n"
        "1. هر گونه سوء استفاده ممنوع است.\n"
        "2. مسئولیت امنیت کیف پول با کاربر است.\n"
        "3. از ارسال اطلاعات حساس خود به افراد دیگر خودداری کنید.\n"
        "4. هرگونه انتقال مالی فقط با تایید مدیریت امکان‌پذیر است.\n"
        "5. پشتیبانی فقط از طریق این ربات انجام می‌شود."
    )
    await message.answer(rules_text, reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))


# --- منوی افزایش موجودی (نمایش گزینه‌ها) ---
@dp.message_handler(lambda m: m.text == "افزایش موجودی")
async def cmd_topup(message: types.Message):
    # نمایش منوی گزینه‌های افزایش موجودی با دکمه‌های inline
    await message.answer(
        "لطفا روش افزایش موجودی را انتخاب کنید:",
        reply_markup=topup_method_keyboard()
    )


# --- هندلر دکمه‌های افزایش موجودی ---
@dp.callback_query_handler(lambda c: c.data.startswith("topup_"))
async def topup_method_selected(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id

    if callback_query.data == "topup_gateway_disabled":
        await callback_query.answer("درگاه پرداخت فعلا غیرفعال است.", show_alert=True)
        return

    if callback_query.data == "topup_back":
        is_admin_user = await is_admin(user_id)
        await callback_query.message.edit_text(
            "منوی اصلی:",
            reply_markup=None
        )
        await bot.send_message(user_id, "به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard(is_admin_user))
        await state.finish()
        return

    if callback_query.data == "topup_card":
        await callback_query.message.edit_text(
            "روش کارت به کارت انتخاب شد.\n"
            "لطفا مبلغ مورد نظر برای افزایش موجودی را وارد کنید.\n"
            "برای لغو، دکمه 'انصراف' را بزنید.",
            reply_markup=cancel_keyboard()
        )
        await TopUpStates.waiting_for_topup_amount.set()
        await state.update_data(topup_method="card")
        await callback_query.answer()
        return

    if callback_query.data == "topup_giftcode":
        await callback_query.message.edit_text(
            "روش کد هدیه انتخاب شد.\n"
            "لطفا کد هدیه خود را وارد کنید.\n"
            "برای لغو، دکمه 'انصراف' را بزنید.",
            reply_markup=cancel_keyboard()
        )
        await TopUpStates.waiting_for_giftcode.set()
        await state.update_data(topup_method="giftcode")
        await callback_query.answer()
        return


# --- دریافت مبلغ کارت به کارت ---
@dp.message_handler(state=TopUpStates.waiting_for_topup_amount)
async def topup_amount_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("افزایش موجودی لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        await state.finish()
        return

    # بررسی عدد بودن مبلغ و مثبت بودن
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("مبلغ باید یک عدد صحیح بزرگتر از صفر باشد. لطفا دوباره وارد کنید یا 'انصراف' بزنید.")
        return

    # ذخیره مبلغ و درخواست عکس رسید
    await state.update_data(amount=amount)
    await message.answer(
        f"لطفا عکس رسید کارت به کارت را ارسال کنید.\n"
        f"مبلغ: {amount} تومان\n"
        f"برای لغو 'انصراف' را بزنید."
    )
    await TopUpStates.waiting_for_card_receipt_photo.set()


# --- دریافت عکس رسید کارت به کارت ---
@dp.message_handler(content_types=types.ContentType.PHOTO, state=TopUpStates.waiting_for_card_receipt_photo)
async def topup_receipt_photo_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await message.answer("مشکلی پیش آمده است. لطفا مجدداً شروع کنید.")
        await state.finish()
        return

    photo = message.photo[-1]
    photo_file_id = photo.file_id
    user_id = message.from_user.id

    # ذخیره رسید در دیتابیس
    await save_receipt(user_id, amount, photo_file_id)

    await message.answer_sticker("CAACAgIAAxkBAAEJfMRhUPEF5vW3fPEJ3-MzWYaA0ZrP4AACVgIAAtF0BEv1RhA6pVtiSCQE")  # استیکر تایید (مثال)

    await message.answer(
        f"رسید شما با موفقیت ثبت شد.\n"
        f"پس از تایید مدیریت، موجودی شما افزایش خواهد یافت.\n"
        f"از صبر شما سپاسگزاریم.",
        reply_markup=main_menu_keyboard(await is_admin(user_id))
    )
    await state.finish()


# --- دریافت کد هدیه ---
@dp.message_handler(state=TopUpStates.waiting_for_giftcode)
async def gift_code_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("افزایش موجودی لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        await state.finish()
        return

    code = message.text.strip()
    user_id = message.from_user.id

    amount = await check_gift_code(code)
    if amount > 0:
        # حذف کد هدیه پس از استفاده
        await delete_gift_code(code)
        # افزودن موجودی به کاربر
        await update_user_balance(user_id, amount)
        await message.answer_sticker("CAACAgIAAxkBAAEJfMRhUPEF5vW3fPEJ3-MzWYaA0ZrP4AACVgIAAtF0BEv1RhA6pVtiSCQE")  # استیکر تایید
        await message.answer(f"کد هدیه با موفقیت استفاده شد.\nموجودی شما به مقدار {amount} تومان افزایش یافت.",
                             reply_markup=main_menu_keyboard(await is_admin(user_id)))
        await state.finish()
    else:
        await message.answer("کد هدیه معتبر نیست یا قبلا استفاده شده است.\nلطفا دوباره وارد کنید یا 'انصراف' بزنید.")


# --- منوی انتقال موجودی ---
@dp.message_handler(lambda m: m.text == "انتقال موجودی")
async def transfer_menu(message: types.Message):
    await message.answer(
        "لطفا آدرس کیف پول مقصد را وارد کنید.\n"
        "برای لغو دکمه 'انصراف' را بزنید.",
        reply_markup=cancel_keyboard()
    )
    await TransferStates.waiting_for_wallet.set()


# --- دریافت آدرس کیف پول مقصد ---
@dp.message_handler(state=TransferStates.waiting_for_wallet)
async def transfer_wallet_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("انتقال موجودی لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        await state.finish()
        return

    wallet_address = message.text.strip()
    # اینجا می‌توانید اعتبارسنجی آدرس را اضافه کنید
    if len(wallet_address) < 5:
        await message.answer("آدرس کیف پول نامعتبر است. دوباره وارد کنید یا 'انصراف' را بزنید.")
        return

    await state.update_data(wallet_address=wallet_address)
    await message.answer(
        "مقدار مبلغ انتقال را وارد کنید.\n"
        "برای لغو 'انصراف' را بزنید.",
        reply_markup=cancel_keyboard()
    )
    await TransferStates.waiting_for_amount.set()


# --- دریافت مبلغ انتقال ---
@dp.message_handler(state=TransferStates.waiting_for_amount)
async def transfer_amount_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("انتقال موجودی لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        await state.finish()
        return

    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("مبلغ باید عدد صحیح مثبت باشد. دوباره وارد کنید یا 'انصراف' بزنید.")
        return

    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    if amount > balance:
        await message.answer(f"موجودی شما کافی نیست. موجودی فعلی: {balance} تومان\nلطفا مبلغ کمتر وارد کنید یا 'انصراف' بزنید.")
        return

    data = await state.get_data()
    wallet_address = data.get("wallet_address")

    # انجام انتقال (اینجا فقط کسر موجودی و فرض انجام انتقال)
    success = await update_user_balance(user_id, -amount)
    if not success:
        await message.answer("خطا در انتقال موجودی. لطفا دوباره تلاش کنید.")
        return

    # اینجا باید انتقال به آدرس مورد نظر ثبت یا ارسال شود
    await message.answer_sticker("CAACAgIAAxkBAAEJfMhhUQ1vTwMlBaLs0NZ4b4FHw5Y0xQACZQIAAtF0BEv11HP9fIpo5iQE")  # استیکر تایید انتقال
    await message.answer(
        f"انتقال با موفقیت انجام شد.\n"
        f"مبلغ {amount} تومان به کیف پول {wallet_address} ارسال شد.",
        reply_markup=main_menu_keyboard(await is_admin(user_id))
    )
    await state.finish()


# --- منوی ارتباط با پشتیبانی ---
@dp.message_handler(lambda m: m.text == "ارتباط با پشتیبانی")
async def support_start(message: types.Message):
    await message.answer(
        "لطفا پیام خود را برای پشتیبانی ارسال کنید.\n"
        "برای لغو 'انصراف' را بزنید.",
        reply_markup=cancel_keyboard()
    )
    await SupportStates.waiting_for_message.set()


# --- دریافت پیام پشتیبانی ---
@dp.message_handler(state=SupportStates.waiting_for_message)
async def support_message_handler(message: types.Message, state: FSMContext):
    if message.text == "انصراف":
        await message.answer("ارسال پیام پشتیبانی لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        await state.finish()
        return

    await save_support_message(message.from_user.id, message.text)
    await message.answer_sticker("CAACAgIAAxkBAAEJfMRhUPEF5vW3fPEJ3-MzWYaA0ZrP4AACVgIAAtF0BEv1RhA6pVtiSCQE")  # استیکر تایید
    await message.answer("پیام شما به پشتیبانی ارسال شد. در اسرع وقت پاسخ داده خواهد شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
    await state.finish()


# --- منوی پنل مدیریت (فقط برای ادمین‌ها) ---
@dp.message_handler(lambda m: m.text == "پنل مدیریت")
async def admin_panel(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("شما اجازه دسترسی به پنل مدیریت را ندارید.")
        return

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton("مشاهده گزارش‌ها"),
        KeyboardButton("مدیریت رسیدها"),
        KeyboardButton("بازگشت به منوی اصلی"),
    )
    await message.answer("به پنل مدیریت خوش آمدید.", reply_markup=kb)


# --- دکمه بازگشت به منوی اصلی ---
@dp.message_handler(lambda m: m.text == "بازگشت" or m.text == "بازگشت به منوی اصلی")
async def back_to_main_menu(message: types.Message):
    is_admin_user = await is_admin(message.from_user.id)
    await message.answer("به منوی اصلی بازگشتید.", reply_markup=main_menu_keyboard(is_admin_user))
    await dp.current_state(user=message.from_user.id).finish()


# --- لغو فرایند با دستور انصراف در هر مرحله ---
@dp.message_handler(lambda m: m.text == "انصراف", state="*")
async def cancel_process(message: types.Message, state: FSMContext):
    await message.answer("فرایند لغو شد.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
    await state.finish()


# ====== راه‌اندازی دیتابیس و استارت ربات ======
if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    executor.start_polling(dp, skip_updates=True)

