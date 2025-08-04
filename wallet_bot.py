from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputSticker
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# توکن ربات
TOKEN = '7092562641:AAEq2jTy1sXIdAXJXzuYwCqTjEd4PjnXgCI'

# اطلاعات کاربران
admins = ['admin_telegram_id']  # ایدی تلگرام ادمین اصلی
users = {}  # دیکشنری ذخیره اطلاعات کاربران (برای مدیریت موجودی و وضعیت عضویت)

# استیکرهایی که میخوای استفاده کنی
sticker = "استیکر_آیدی"  # استیکر برای خوشامدگویی یا تعامل

# تابع شروع ربات
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    # چک کردن عضویت
    if user_id not in users:
        update.message.reply_text("برای استفاده از ربات باید عضو بشید. لطفا از دکمه زیر برای عضویت استفاده کنید.")
        # دکمه برای عضویت
        keyboard = [[InlineKeyboardButton("عضویت", callback_data='signup')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("برای عضویت بر روی دکمه کلیک کن.", reply_markup=reply_markup)
    else:
        # اگر کاربر عضو بود، خوشامدگویی
        update.message.reply_text(f"سلام {update.message.from_user.first_name}! خوش اومدی به ربات کیف پول رزومیت!")

# تابع عضویت
def signup(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    if user_id not in users:
        users[user_id] = {"balance": 0, "role": "user"}  # اطلاعات کاربر و موجودی
        update.callback_query.answer("شما با موفقیت عضو شدید.")
        update.callback_query.edit_message_text(f"سلام! خوش اومدی به ربات. موجودی شما: {users[user_id]['balance']} PXT")
    else:
        update.callback_query.answer("شما قبلاً عضو شدید.")

# تابع مدیریت موجودی
def balance(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in users:
        balance = users[user_id]['balance']
        update.message.reply_text(f"موجودی شما: {balance} PXT")
    else:
        update.message.reply_text("شما هنوز عضو نشده‌اید. برای عضویت از دستور /start استفاده کنید.")

# تابع مدیریت دسترسی به ادمین
def admin_panel(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if str(user_id) in admins:
        keyboard = [
            [InlineKeyboardButton("افزودن موجودی به کاربر", callback_data='add_balance')],
            [InlineKeyboardButton("نمایش لیست کاربران", callback_data='list_users')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("پنل مدیریت:", reply_markup=reply_markup)
    else:
        update.message.reply_text("شما اجازه دسترسی به این بخش را ندارید.")

# دستورات برای ادمین
def admin_actions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == 'add_balance':
        # اینجا کد مربوط به افزودن موجودی به کاربر رو می‌نویسیم
        query.edit_message_text("برای افزودن موجودی، آی‌دی کاربر و مقدار رو وارد کن.")
        # این قسمت به ورود اطلاعات نیاز داره، مثلاً پیام بعدی به کاربر اطلاعات ورود رو درخواست میکنه.
    elif query.data == 'list_users':
        # نمایش لیست کاربران
        user_list = "\n".join([f"{user_id}: {info['balance']} PXT" for user_id, info in users.items()])
        query.edit_message_text(f"لیست کاربران:\n{user_list}")

# استیکر برای خوشامدگویی
def send_sticker(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in users:
        update.message.reply_sticker(sticker)

# تابع اصلی که ربات رو اجرا میکنه
def main():
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # دستورات اصلی
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("admin", admin_panel))
    dispatcher.add_handler(CallbackQueryHandler(signup, pattern='signup'))
    dispatcher.add_handler(CallbackQueryHandler(admin_actions, pattern='add_balance|list_users'))
    dispatcher.add_handler(MessageHandler(Filters.sticker, send_sticker))  # استفاده از استیکر

    # شروع ربات
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
