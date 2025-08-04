import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
import logging
import os

# تنظیمات اولیه
API_TOKEN = os.getenv('API_TOKEN')  # متغیر محیطی توکن ربات
admin_main = []  # مدیران اصلی به صورت لیست
admin_simple = []  # مدیران ساده به صورت لیست
join_required = True  # جوین اجباری فعال است یا نه
admin_code = "SECRET_CODE"  # کد مخفی برای مدیر اصلی
channel_link = ''  # لینک کانال که اعضا باید به آن بپیوندند
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ایجاد دیتابیس
def create_db():
    conn = sqlite3.connect('wallet.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER, joined BOOLEAN)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, role TEXT)''')  # برای ذخیره مدیران
    conn.commit()
    conn.close()

# گرفتن موجودی کاربر
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

# ایجاد دکمه‌ها و منوها (منوی شیشه‌ای)
def create_main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)  # دکمه‌ها را در دو ستون نمایش می‌دهیم
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
    keyboard.add(InlineKeyboardButton("تنظیمات جوین اجباری", callback_data="set_join_required"))
    return keyboard

# دکمه شیشه‌ای برای پیوستن به کانال و بررسی عضویت
def create_join_check_buttons():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("پیوستن به کانال", url=f"https://t.me/{channel_link}"))
    keyboard.add(InlineKeyboardButton("بررسی عضویت", callback_data="check_membership"))
    return keyboard

# دستور شروع
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if join_required:
        if not await check_membership(user_id):
            # نمایش دکمه شیشه‌ای برای عضویت و بررسی عضویت
            await message.answer(f"سلام {message.from_user.first_name} عزیز! \n\nبرای استفاده از ربات باید به کانال {channel_link} بپیوندید.", 
                                 reply_markup=create_join_check_buttons())
            return
    if user_id in admin_main:
        await message.answer("سلام مدیر اصلی! خوش اومدی! به ربات کیف پول دیجیتال خوش آمدید.\nبرای دسترسی به پنل مدیریت از منوی زیر استفاده کن.", 
                             reply_markup=create_admin_panel())
    else:
        await message.answer("سلام! خوش اومدی به ربات کیف پول دیجیتال.\nبرای مشاهده موجودی و دسترسی به سایر امکانات از منوی زیر استفاده کن:", 
                             reply_markup=create_main_menu())

# بررسی عضویت کاربر در کانال
async def check_membership(user_id):
    if join_required:
        try:
            member = await bot.get_chat_member(channel_link, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception:
            return False
    return True

# بررسی عضویت از دکمه شیشه‌ای
@dp.callback_query_handler(lambda c: c.data == "check_membership")
async def check_membership_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if await check_membership(user_id):
        await bot.answer_callback_query(callback_query.id, text="شما به کانال ملحق شده‌اید.")
    else:
        await bot.answer_callback_query(callback_query.id, text="شما هنوز به کانال عضو نشده‌اید. لطفاً عضو شوید.")

# دستورات ادمین
@dp.message_handler(commands=['admin_panel'])
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id in admin_main:
        await message.answer("پنل مدیریت:\n1. مدیران\n2. افزایش موجودی\n3. تنظیمات جوین اجباری", reply_markup=create_admin_panel())
    else:
        await message.answer("شما دسترسی به پنل مدیریت ندارید.")

# ثبت مدیر اصلی
@dp.callback_query_handler(lambda c: c.data == "register_admin")
async def register_admin(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "لطفاً کد مدیر اصلی را وارد کنید:")

@dp.message_handler(lambda message: message.text == admin_code)
async def set_admin(message: types.Message):
    user_id = message.from_user.id
    if user_id not in admin_main:
        admin_main.append(user_id)
        await message.answer("شما به عنوان مدیر اصلی ثبت شدید.", reply_markup=create_admin_panel())
    else:
        await message.answer("شما قبلاً به عنوان مدیر اصلی ثبت شدید.")

# ثبت مدیر ساده توسط مدیر اصلی
@dp.message_handler(commands=['add_admin'])
async def add_admin(message: types.Message):
    if message.from_user.id in admin_main:
        link = f"https://t.me/{bot.username}?start={message.from_user.id}"  # لینک خاص برای اضافه کردن مدیر
        await message.answer(f"برای افزودن مدیر ساده، این لینک را ارسال کن: {link}")
    else:
        await message.answer("شما دسترسی به این فرمان ندارید.")

# ثبت مدیر ساده از طریق لینک
@dp.message_handler(commands=['start'])
async def cmd_start_admin(message: types.Message):
    if message.text.startswith("/start"):
        referrer_id = message.text.split()[-1]
        if referrer_id.isdigit() and int(referrer_id) in admin_main:
            admin_simple.append(message.from_user.id)
            await message.answer("شما به عنوان مدیر ساده ثبت شدید.")
        else:
            await message.answer("این لینک معتبر نیست.")

# نمایش مدیران برای مدیر اصلی
@dp.callback_query_handler(lambda c: c.data == "manage_admins")
async def manage_admins(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_main:
        admin_list = "\n".join([str(admin) for admin in admin_main])  # مدیران اصلی
        admin_simple_list = "\n".join([str(admin) for admin in admin_simple])  # مدیران ساده
        await callback_query.answer()
        await callback_query.message.answer(f"مدیران اصلی:\n{admin_list}\n\nمدیران ساده:\n{admin_simple_list}")
    else:
        await callback_query.answer("شما دسترسی به این بخش ندارید.")

# جوین اجباری
@dp.callback_query_handler(lambda c: c.data == "set_join_required")
async def set_join_required(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_main:
        global join_required
        join_required = not join_required
        status = "فعال" if join_required else "غیرفعال"
        await callback_query.answer(f"جوین اجباری {status} شد.")
    else:
        await callback_query.answer("شما دسترسی به این بخش ندارید.")

# افزایش موجودی
@dp.callback_query_handler(lambda c: c.data == "increase_balance")
async def increase_balance(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_main:
        await callback_query.answer("برای افزایش موجودی، شناسه کاربر و مقدار را وارد کنید.")
    else:
        await callback_query.answer("شما دسترسی به این بخش ندارید.")

# اجرای ربات
if __name__ == '__main__':
    create_db()  # ساخت دیتابیس
    executor.start_polling(dp, skip_updates=True)
