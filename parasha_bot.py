import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          ContextTypes, JobQueue)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import time, timedelta
from dotenv import load_dotenv

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set your bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Global dict to hold language per user
user_languages = {}

# Example messages for parasha
WEEKLY_PARASHA_SHORT = {
    'en': "🪶 Weekly Parshah (brief): This week's portion is 'Korach'.",
    'he': "🪶 פרשת השבוע בקצרה: פרשת קורח.",
    'ru': "🪶 Краткая глава недели: Парашат Корах."
}

WEEKLY_PARASHA_FULL = {
    'en': "📜 Full Weekly Parshah: This week's Torah portion is 'Korach', describing the rebellion...",
    'he': "📜 פרשת השבוע המלאה: בפרשת קורח מסופר על המרד...",
    'ru': "📜 Полный текст главы недели: Парашат Корах рассказывает о восстании..."
}

# Language buttons with emojis
LANG_BUTTONS = [
    [InlineKeyboardButton("🇬🇧 English", callback_data="lang|en")],
    [InlineKeyboardButton("🇮🇱 עברית", callback_data="lang|he")],
    [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang|ru")],
]

COMMANDS = [
    ("start", "Start the bot and set language"),
    ("language", "Change bot language"),
    ("brief", "Weekly Parshah (brief)"),
    ("full", "Weekly Parshah (full)")
]

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_languages[user_id] = 'en'  # default to English
    await update.message.reply_text(
        "Welcome! Choose your language:",
        reply_markup=InlineKeyboardMarkup(LANG_BUTTONS)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = query.data.split('|')[1]
    user_languages[user_id] = lang
    await query.edit_message_text(f"✅ Language set to {lang.upper()}")

async def send_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_languages.get(update.effective_user.id, 'en')
    await update.message.reply_text(WEEKLY_PARASHA_SHORT[lang])

async def send_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_languages.get(update.effective_user.id, 'en')
    await update.message.reply_text(WEEKLY_PARASHA_FULL[lang])

# --- Job Queue Broadcasts ---

async def scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE):
    for user_id, lang in user_languages.items():
        try:
            await context.bot.send_message(chat_id=user_id, text=WEEKLY_PARASHA_SHORT[lang])
        except Exception as e:
            logger.warning(f"Failed to send to {user_id}: {e}")

# --- Application Entry ---

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("language", start))
app.add_handler(CommandHandler("brief", send_brief))
app.add_handler(CommandHandler("full", send_full))
app.add_handler(CallbackQueryHandler(lang_callback, pattern=r"^lang\|"))

# Set visible commands in Telegram UI
app.bot.set_my_commands([CommandHandler(name, desc) for name, desc in COMMANDS])

# Schedule the broadcast at 12:20 Dubai time daily
scheduler = AsyncIOScheduler(timezone="Asia/Dubai")
scheduler.add_job(lambda: scheduled_broadcast(app.bot), 'cron', hour=12, minute=20)
scheduler.start()

# --- Run the bot ---
if __name__ == '__main__':
    app.run_polling()
