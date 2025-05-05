import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

# Stages
USERNAME, CONFIRM_USERNAME, AWAITING_SCREENSHOT = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Please enter your *username* to proceed:", parse_mode=ParseMode.MARKDOWN)
    return USERNAME

async def collect_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text
    context.user_data['username'] = username

    keyboard = [
        [InlineKeyboardButton("✅ Yes", callback_data="yes")],
        [InlineKeyboardButton("❌ No", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🔍 You entered: *{username}*\n\nDo you want to confirm?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return CONFIRM_USERNAME

async def confirm_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "yes":
        await query.edit_message_text("⏳ Please wait, loading...")
        await fake_loading(query, context)
        return AWAITING_SCREENSHOT
    else:
        await query.edit_message_text("❗️Please re-enter your username:")
        return USERNAME

async def fake_loading(query, context):
    username = context.user_data['username']  # Get the username from context
    for i in range(3):
        await query.edit_message_text(f"⏳ Processing{'.' * (i+1)}")
        await context.application.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
        await context.application.create_task(wait(1))

    # Update the message with the desired text after loading
    await query.edit_message_text(
        f"🔓 Password for *{username}* has been cracked. Please pay on the below QR code to get the password.",
        parse_mode=ParseMode.MARKDOWN
    )

    with open("qr.png", "rb") as qr_file:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=qr_file,
            caption="📥 *Scan to Pay using UPI and then confirm below:*",
            parse_mode=ParseMode.MARKDOWN
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="After completing the payment, send payment screenshot."
        )


async def wait(seconds):
    import asyncio
    await asyncio.sleep(seconds)

# Screenshot Handler
async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        user = update.effective_user
        photo_file = update.message.photo[-1]
        file = await context.bot.get_file(photo_file.file_id)

        # Download screenshot locally (optional)
        screenshot_path = f"screenshots/{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        os.makedirs("screenshots", exist_ok=True)
        await file.download_to_drive(screenshot_path)

        # Notify user
        await update.message.reply_text("Thank you! Your payment is being verified. Password will be delivered after 5 minutes.")

        # Notify admin
        caption = f"🧾 *Payment Screenshot Received!*\n\n👤 User: `{user.first_name}` (`{user.id}`)\n🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo_file.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
        
        return ConversationHandler.END
    else:
        await update.message.reply_text("Please send a valid screenshot (image).")
        return AWAITING_SCREENSHOT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Process cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_username)],
            CONFIRM_USERNAME: [CallbackQueryHandler(confirm_username)],
            AWAITING_SCREENSHOT: [MessageHandler(filters.PHOTO, screenshot_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
