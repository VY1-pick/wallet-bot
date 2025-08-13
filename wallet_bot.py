# -*- coding: utf-8 -*-

# بخش کتابخانه ها
import asyncio
import logging
import sys

#from os import getenv
from aiogram import Bot, Dispatcher
from aiogram.utils import html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message


# بخش متغییر ها

# برای امنیت بیشتر توکن
# for up token secure

##Token = getenv("BOT_TOKEN")

# Bot token can be obtained via https://t.me/BotFather
# توکن ربات خود را از https://t.me/BotFather دریافت کنید

##Token = 'Your-Bot-Token'
Token = '8225379240:AAE-kozMmVfw84hTsvpSN0rWUyjAe5tRc7U'

# All handlers should be attached to the Router (or Dispatcher)
# تمامیی هندلر (کنترلر) ها باید به روتر متصل باشند (یا Dispatcher)

dp = Dispatcher()


# بخش هندلر ها
@dp.message(CommandStart())
async def Start_message_handler(message: Message) -> None:
    # این هندلر، پیام‌های حاوی دستور /start را دریافت و پردازش می‌کند.
    # This handler receives messages with `/start` command

    await message.answer(f"🎉✨ سلام {html.bold(message.from_user.full_name)}!\tبه ربات PiXi Manager خوش آمدید ✨🎉\n🤖 دستیار هوشمند و همه‌فن‌حریف شما برای مدیریت حرفه‌ای 📢 کانال‌ها و 💬 گروه‌ها\n⚡ با امکانات پیشرفته، سرعت بالا و کنترل کامل؛ تجربه‌ای جدید از مدیریت را آغاز کنید! 🚀\n📍 آماده‌اید؟ همین حالا شروع کنید و مدیریت را لذت‌بخش‌تر کنید! 💼🔥")

















# بخش پیکربندی و اجرای ربات
async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    # ایجاد یک نمونه از بات و مقداردهی اولیه آن با ویژگی‌های پیش‌فرض، که در تمام فراخوانی های API مورد استفاده قرار میگیرد

    bot = Bot(token=Token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    # شروع فرآیند دریافت و پردازش رویدادها از طریق polling
    print("Bot is Running! Please Start")
    await dp.start_polling(bot)

# Run the program only if this file is executed directly,
# configure logging at INFO level, and execute the main function using asyncio
# اجرای برنامه در صورتی که این فایل به صورت مستقیم اجرا شود،
# پیکربندی لاگ‌گیری در سطح INFO و اجرای تابع اصلی با استفاده از asyncio

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

