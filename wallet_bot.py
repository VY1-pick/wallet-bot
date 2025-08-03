import os
import logging
from aiogram import Bot, Dispatcher, executor, types
import aiosqlite
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_CODE = "123456"  # کد ثابت ثبت مدیر (مثلاً تغییر بده به کد خودت)
CARD_NUMBER = "5022291530689296"
CARD_OWNER = "ملکی"

# تنظیم لاگ
logging.basicConfig(level=logging.INFO)

# راه‌اندازی بات و دیسپچر با حافظه حالت
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# حالات FSM برای فرایند کارت به کارت و افزایش موجودی
class TopUpStates(StatesGroup):
    choosing_method = State()
    entering_amount = State()
    waiting_for_deposit_confirm = State()
    waiting_for_receipt = State()

class MessageToUserStates(StatesGroup):
    waiting_for_message = State()

class AdminRegisterStates(StatesGroup):
    waiting_for_code = State()

# راه‌اندازی دیتابیس
async def init_db():
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.commit()

# منوی اصلی شیشه‌ای
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
        InlineKeyboardButton("💰 افزایش موجودی", callback_data="topup"),
        InlineKeyboardButton("🏦 کارت به کارت", callback_data="card_to_card"),
        InlineKeyboardButton("📞 ارتباط با پشتیبانی", callback_data="support")
    )
    return keyboard

# منوی ثبت مدیر (نمایش اگر مدیر ثبت نشده)
def admin_register_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("ثبت مدیر", callback_data="register_admin"))
    return keyboard

# استارت ربات
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user is None:
            await db.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)",
                             (user_id, username, 0))
            await db.commit()
            welcome_text = "👋 خوش آمدی! حساب کیف پولت ساخته شد."
        else:
            welcome_text = "👋 دوباره خوش آمدی!"

        # بررسی اینکه کاربر مدیر است یا نه
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        is_admin = (await cursor.fetchone())[0]

    # اگر مدیر نیست، دکمه ثبت مدیر را نشان بده
    if not is_admin:
        await message.answer(welcome_text, reply_markup=admin_register_menu())
    else:
        await message.answer(welcome_text, reply_markup=main_menu())

# ثبت مدیر
@dp.callback_query_handler(lambda c: c.data == "register_admin")
async def register_admin_start(callback_query: types.CallbackQuery):
    await AdminRegisterStates.waiting_for_code.set()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "کد مدیر را وارد کنید:")

@dp.message_handler(state=AdminRegisterStates.waiting_for_code)
async def register_admin_code(message: types.Message, state: FSMContext):
    if message.text == ADMIN_CODE:
        async with aiosqlite.connect("wallet.db") as db:
            await db.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (message.from_user.id,))
            await db.commit()
        await message.answer("✅ شما به عنوان مدیر ثبت شدید.", reply_markup=main_menu())
    else:
        await message.answer("❌ کد مدیر اشتباه است. دوباره تلاش کنید:")
        return
    await state.finish()

# نمایش پروفایل
@dp.callback_query_handler(lambda c: c.data == "profile")
async def show_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT username, balance FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
    if user:
        username, balance = user
        text = (
            f"👤 نام کاربری: @{username}\n"
            f"🆔 آی‌دی عددی: {user_id}\n"
            f"🏦 آدرس کیف پول: wallet_{user_id}\n"
            f"💰 موجودی: {balance} تومان\n"
            f"🔗 وضعیت اتصال به سایت: متصل نشده"
        )
    else:
        text = "❗ حسابی برای شما پیدا نشد. لطفاً /start را بزنید."
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, text, reply_markup=main_menu())

# انتخاب روش افزایش موجودی (فقط کارت به کارت فعال)
@dp.callback_query_handler(lambda c: c.data == "topup")
async def topup_start(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("کارت به کارت 🏦", callback_data="method_card_to_card"))
    await bot.send_message(callback_query.from_user.id, "لطفاً روش افزایش موجودی را انتخاب کنید:", reply_markup=keyboard)

# انتخاب روش کارت به کارت
@dp.callback_query_handler(lambda c: c.data == "method_card_to_card")
async def card_to_card_method(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await TopUpStates.entering_amount.set()
    await bot.send_message(callback_query.from_user.id, "مبلغ مورد نظر را به تومان وارد کنید:")

# دریافت مبلغ
@dp.message_handler(state=TopUpStates.entering_amount)
async def receive_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError()
    except:
        await message.reply("❌ لطفاً فقط عدد صحیح بزرگ‌تر از صفر وارد کنید.")
        return
    await state.update_data(amount=amount)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("تأیید واریز", callback_data="confirm_deposit"),
        InlineKeyboardButton("انصراف", callback_data="cancel_deposit")
    )
    await TopUpStates.waiting_for_deposit_confirm.set()
    await message.answer(f"مبلغ {amount} تومان برای واریز انتخاب شده.\n"
                         f"شماره کارت واریز:\n{CARD_NUMBER}\n"
                         f"به نام: {CARD_OWNER}\n\n"
                         "پس از واریز، دکمه 'تأیید واریز' را بزنید.", reply_markup=keyboard)

# تأیید واریز یا انصراف
@dp.callback_query_handler(lambda c: c.data in ["confirm_deposit", "cancel_deposit"], state=TopUpStates.waiting_for_deposit_confirm)
async def confirm_or_cancel_deposit(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "confirm_deposit":
        await bot.answer_callback_query(callback_query.id, "لطفاً عکس رسید واریز را ارسال کنید.")
        await TopUpStates.waiting_for_receipt.set()
    else:
        await bot.answer_callback_query(callback_query.id, "عملیات افزایش موجودی لغو شد.")
        await state.finish()
    await bot.edit_message_reply_markup(callback_query.from_user.id, callback_query.message.message_id, reply_markup=None)

# دریافت عکس رسید
@dp.message_handler(content_types=types.ContentType.PHOTO, state=TopUpStates.waiting_for_receipt)
async def receive_receipt(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    photo = message.photo[-1]  # با کیفیت‌ترین عکس
    file_id = photo.file_id
    data = await state.get_data()
    amount = data.get("amount")

    # ذخیره درخواست به دیتابیس
    async with aiosqlite.connect("wallet.db") as db:
        await db.execute("INSERT INTO deposits (user_id, amount, receipt_file_id, status) VALUES (?, ?, ?, ?)",
                         (user_id, amount, file_id, "pending"))
        await db.commit()

    await message.answer("✅ رسید شما ثبت شد. پس از بررسی توسط مدیر، موجودی شما افزایش خواهد یافت.\n"
                         "تا آن زمان صبور باشید.")
    await state.finish()

    # اطلاع به مدیرها
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE is_admin=1")
        admins = await cursor.fetchall()

    for admin in admins:
        admin_id = admin[0]
        text = (f"📥 رسید جدید واریز:\n"
                f"👤 کاربر: @{message.from_user.username or ''} (ID: {user_id})\n"
                f"💰 مبلغ: {amount} تومان\n"
                f"وضعیت: در انتظار بررسی")
        keyboard = InlineKeyboardMarkup(row_width=3)
        keyboard.add(
            InlineKeyboardButton("✅ تأیید واریزی", callback_data=f"approve_{user_id}_{amount}"),
            InlineKeyboardButton("❌ واریزی فیک", callback_data=f"fake_{user_id}_{amount}"),
            InlineKeyboardButton("💬 پیام به کاربر", callback_data=f"msg_{user_id}")
        )
        await bot.send_photo(admin_id, photo=file_id, caption=text, reply_markup=keyboard)

# مدیریت دکمه‌های تأیید واریزی، فیک و پیام به کاربر برای مدیر
@dp.callback_query_handler(lambda c: c.data.startswith(("approve_", "fake_", "msg_")))
async def admin_actions(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    admin_id = callback_query.from_user.id

    # بررسی مدیر بودن کاربر
    async with aiosqlite.connect("wallet.db") as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (admin_id,))
        res = await cursor.fetchone()
    if not res or res[0] == 0:
        await bot.answer_callback_query(callback_query.id, "❌ شما مدیر نیستید.")
        return

    if data.startswith("approve_"):
        _, user_id_str, amount_str = data.split("_")
        user_id = int(user_id_str)
        amount = int(amount_str)
        async with aiosqlite.connect("wallet.db") as db:
            # بروزرسانی موجودی کاربر
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            # تغییر وضعیت رسید به approved
            await db.execute("UPDATE deposits SET status='approved' WHERE user_id=? AND amount=? AND status='pending'",
                             (user_id, amount))
            await db.commit()
        await bot.answer_callback_query(callback_query.id, "✅ واریز تأیید شد.")
        await bot.send_message(user_id, f"✅ واریز مبلغ {amount} تومان توسط مدیر تأیید شد و به کیف پول شما اضافه گردید.")
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id, reply_markup=None)

    elif data.startswith("fake_"):
        _, user_id_str, amount_str = data.split("_")
        user_id = int(user_id_str)
        amount = int(amount_str)
        async with aiosqlite.connect("wallet.db") as db:
            await db.execute("UPDATE deposits SET status='fake' WHERE user_id=? AND amount=? AND status='pending'",
                             (user_id, amount))
            await db.commit()
        await bot.answer_callback_query(callback_query.id, "❌ واریز به عنوان فیک ثبت شد.")
        await bot.send_message(user_id, f"❌ واریز مبلغ {amount} تومان توسط مدیر رد شد.")
        await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id, reply_markup=None)

    elif data.startswith("msg_"):
        _, user_id_str = data.split("_")
        user_id = int(user_id_str)
        await bot.answer_callback_query(callback_query.id)
        await callback_query.message.answer("✍️ پیام خود را برای کاربر ارسال کنید:")
        await state.update_data(chat_with=user_id)
        await MessageToUserStates.waiting_for_message.set()

# دریافت پیام مدیر برای کاربر
@dp.message_handler(state=MessageToUserStates.waiting_for_message)
async def forward_message_to_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("chat_with")
    if user_id:
        try:
            await bot.send_message(user_id, f"📩 پیام از مدیر:\n\n{message.text}")
            await message.answer("✅ پیام ارسال شد.")
        except Exception as e:
            await message.answer("❌ ارسال پیام به کاربر با مشکل مواجه شد.")
    else:
        await message.answer("❌ گیرنده مشخص نیست.")
    await state.finish()

# منوی کارت به کارت (می‌تواند برای اطلاع رسانی بیشتر یا اطلاعات استفاده شود)
@dp.callback_query_handler(lambda c: c.data == "card_to_card")
async def card_to_card_info(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    text = (
        f"🏦 شماره کارت برای کارت به کارت:\n"
        f"{CARD_NUMBER}\n"
        f"به نام: {CARD_OWNER}\n\n"
        "برای افزایش موجودی از منوی «افزایش موجودی» استفاده کنید."
    )
    await bot.send_message(callback_query.from_user.id, text, reply_markup=main_menu())

# ارتباط با پشتیبانی - ارسال پیام به مدیرها
@dp.callback_query_handler(lambda c: c.data == "support")
async def support_start(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "✍️ پیام خود را برای پشتیبانی ارسال کنید:")
    await MessageToUserStates.waiting_for_message.set()

# مدیریت پیام‌های کاربران به پشتیبانی (ارسال به همه مدیران)
@dp.message_handler(state=MessageToUserStates.waiting_for_message)
async def forward_support_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # اگر این حالت برای ارسال پیام به کاربر نیست، یعنی پیام به پشتیبانیه
    if not data.get("chat_with"):
        async with aiosqlite.connect("wallet.db") as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE is_admin=1")
            admins = await cursor.fetchall()
        sent_to = 0
        for admin in admins:
            try:
                await bot.send_message(admin[0], f"📞 پیام از کاربر @{message.from_user.username or ''} (ID: {message.from_user.id}):\n\n{message.text}")
                sent_to += 1
            except:
                pass
        if sent_to > 0:
            await message.answer("✅ پیام شما به پشتیبانی ارسال شد. منتظر پاسخ باشید.")
        else:
            await message.answer("❌ در حال حاضر هیچ مدیری آنلاین نیست.")
        await state.finish()

# فرمان /balance ساده (اختیاری)
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
    print("✅ ربات آماده است.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
