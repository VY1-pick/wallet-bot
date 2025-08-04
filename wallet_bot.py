import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
import logging
import os

# تنظیمات اولیه
API_TOKEN = os.getenv('API_TOKEN')  # توکن ربات
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ایجاد دیتابیس
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER, joined BOOLEAN)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_requests (user_id INTEGER, amount INTEGER, method TEXT, status TEXT, receipt_url TEXT)''')
    conn.commit()
    conn.close()

# دریافت موجودی کاربر
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

# منوها و دکمه‌ها
def create_main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("مشاهده موجودی", callback_data="balance"),
        InlineKeyboardButton("افزایش موجودی", callback_data="increase_balance")
    )
    keyboard.add(
        InlineKeyboardButton("بررسی عضویت", callback_data="check_membership"),
        InlineKeyboardButton("پنل مدیریت", callback_data="admin_panel")
    )
    keyboard.add(
        InlineKeyboardButton("تنظیمات جوین اجباری", callback_data="set_join_required")
    )
    return keyboard

def create_admin_panel():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("مدیران", callback_data="manage_admins"))
    keyboard.add(InlineKeyboardButton("افزایش موجودی", callback_data="increase_balance"))
    keyboard.add(InlineKeyboardButton("تنظیمات جوین اجباری", callback_data="toggle_join_required"))
    keyboard.add(InlineKeyboardButton("درخواست‌های واریز", callback_data="view_deposit_requests"))
    return keyboard

def create_join_check_buttons():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("پیوستن به کانال", url=f"https://t.me/Info_ResumeIt"))
    keyboard.add(InlineKeyboardButton("بررسی عضویت", callback_data="check_membership"))
    return keyboard

# شروع درخواست افزایش موجودی
@dp.callback_query_handler(lambda c: c.data == "increase_balance")
async def cmd_increase_balance(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("کارت به کارت", callback_data="increase_balance_card"),
        InlineKeyboardButton("درگاه پرداخت", callback_data="increase_balance_gateway")
    )
    await callback_query.message.answer("لطفاً روش افزایش موجودی را انتخاب کنید:", reply_markup=keyboard)

# درخواست افزایش موجودی کارت به کارت
@dp.callback_query_handler(lambda c: c.data == "increase_balance_card")
async def cmd_increase_balance_card(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("PXT", callback_data="increase_balance_amount_PXT"),
        InlineKeyboardButton("تومان", callback_data="increase_balance_amount_toman")
    )
    await callback_query.message.answer("لطفاً واحد پولی مورد نظر را انتخاب کنید (PXT یا تومان):", reply_markup=keyboard)

# انتخاب مبلغ به واحد PXT یا تومان
@dp.callback_query_handler(lambda c: c.data in ["increase_balance_amount_PXT", "increase_balance_amount_toman"])
async def cmd_enter_amount(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if callback_query.data == "increase_balance_amount_PXT":
        await callback_query.message.answer("مقدار PXT را وارد کنید:")
        await dp.current_state(user=user_id).set_state("waiting_for_amount_PXT")
    elif callback_query.data == "increase_balance_amount_toman":
        await callback_query.message.answer("مقدار تومان را وارد کنید:")
        await dp.current_state(user=user_id).set_state("waiting_for_amount_toman")

# دریافت مبلغ از کاربر
@dp.message_handler(state="waiting_for_amount_PXT")
async def get_amount_PXT(message: types.Message, state):
    amount_pxt = message.text
    try:
        amount_pxt = float(amount_pxt)
        amount_toman = amount_pxt * 1000  # تبدیل PXT به تومان
        await message.answer(f"مقدار وارد شده: {amount_pxt} PXT معادل {amount_toman} تومان است.\nلطفاً مبلغ را به شماره کارت 5022291530689296 واریز کنید.")
        await message.answer("پس از واریز، دکمه زیر را بزنید:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("واریز کردم", callback_data="deposit_done")))
        await state.finish()
    except ValueError:
        await message.answer("مقدار وارد شده معتبر نیست. لطفاً دوباره وارد کنید:")

@dp.message_handler(state="waiting_for_amount_toman")
async def get_amount_toman(message: types.Message, state):
    amount_toman = message.text
    try:
        amount_toman = float(amount_toman)
        amount_pxt = amount_toman / 1000  # تبدیل تومان به PXT
        await message.answer(f"مقدار وارد شده: {amount_toman} تومان معادل {amount_pxt} PXT است.\nلطفاً مبلغ را به شماره کارت 5022291530689296 واریز کنید.")
        await message.answer("پس از واریز، دکمه زیر را بزنید:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("واریز کردم", callback_data="deposit_done")))
        await state.finish()
    except ValueError:
        await message.answer("مقدار وارد شده معتبر نیست. لطفاً دوباره وارد کنید:")

# دکمه واریز کردم
@dp.callback_query_handler(lambda c: c.data == "deposit_done")
async def cmd_deposit_done(callback_query: types.CallbackQuery):
    await callback_query.message.answer("لطفاً عکس رسید واریز را ارسال کنید. بعد از ارسال رسید، منتظر تایید ادمین باشید.")

# مدیریت درخواست‌های واریز
@dp.callback_query_handler(lambda c: c.data == "view_deposit_requests")
async def view_deposit_requests(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_main:
        # نمایش درخواست‌های واریز
        conn = sqlite3.connect('wallet.db')
        c = conn.cursor()
        c.execute("SELECT * FROM deposit_requests WHERE status = 'pending'")
        requests = c.fetchall()
        conn.close()

        if not requests:
            await callback_query.message.answer("هیچ درخواست واریزی در انتظار تایید نیست.")
        else:
            for req in requests:
                user_id, amount, method, _, _ = req
                await callback_query.message.answer(f"درخواست افزایش موجودی از کاربر {user_id}:\nمقدار: {amount} {method}\nلطفاً رسید واریز را تایید کنید.")
                await callback_query.message.answer(
                    "دکمه‌های تایید و رد رسید:\n",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("تایید رسید", callback_data=f"approve_{user_id}"),
                        InlineKeyboardButton("رسید فیک", callback_data=f"reject_{user_id}")
                    )
                )
    else:
        await callback_query.answer("شما دسترسی به این بخش ندارید.")

# تایید رسید
@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve_deposit(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    # تایید و اضافه کردن موجودی
    add_balance(user_id, 1000)  # اضافه کردن 1000 PXT به موجودی کاربر
    await callback_query.message.answer(f"درخواست واریز برای کاربر {user_id} تایید شد.")

# رد رسید
@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject_deposit(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    # تغییر وضعیت به "رد شده"
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute("UPDATE deposit_requests SET status = 'rejected' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await callback_query.message.answer(f"درخواست واریز برای کاربر {user_id} رد شد.")

# اجرای Polling
if __name__ == '__main__':
    create_db()  # ساخت دیتابیس
    executor.start_polling(dp, skip_updates=True)
