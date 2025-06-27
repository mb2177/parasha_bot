import logging
import json
import asyncio
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ContextTypes,
)
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# ВСТАВЬТЕ СЮДА ВАШИ КЛЮЧИ (внутри кавычек):
TELEGRAM_BOT_TOKEN = "7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M"
OPENAI_API_KEY     = "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"
LANG_FILE          = "user_langs.json"
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
user_langs = {}

def load_user_langs():
    global user_langs
    try:
        with open(LANG_FILE, "r", encoding="utf-8") as f:
            user_langs = json.load(f)
    except FileNotFoundError:
        user_langs = {}

def save_user_langs():
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(user_langs, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton("Русский", callback_data="lang|ru"),
        InlineKeyboardButton("English", callback_data="lang|en"),
        InlineKeyboardButton("עברית", callback_data="lang|he"),
    ]
    await update.message.reply_text(
        "Выберите язык / Choose your language / בחר שפה:",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    lang = update.callback_query.data.split("|")[1]
    user_langs[str(update.effective_user.id)] = lang
    save_user_langs()
    labels = {"ru": "Русский", "en": "English", "he": "עברית"}
    await update.callback_query.edit_message_text(f"Язык установлен: {labels[lang]}")

async def generate_parasha_summary(lang: str) -> str:
    if lang == "en":
        system = "You are an expert on the Torah, explaining its weekly portion simply in English."
        prompt = "Write a simple summary of this week's Torah portion for those unfamiliar with religious texts."
    elif lang == "he":
        system = "אתה מומחה לתורה ומסביר את הפרשה השבועית בפשטות בעברית."
        prompt = "כתוב תקציר פשוט של הפרשה השבועית עבור מי שלא מכיר טקסטים דתיים."
    else:
        system = "Ты эксперт по еврейским текстам и умеешь объяснять их простым языком."
        prompt = "Напиши простым языком краткий пересказ текущей недельной главы Торы."
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_midweek_reflection(lang: str) -> str:
    if lang == "en":
        system = "You are a wise mentor and list reflection points clearly in English."
        prompt = "List key lessons and reflection points from this week's Torah portion midweek."
    elif lang == "he":
        system = "אתה מורה חכם ורושם נקודות חשיבה ברורות בעברית."
        prompt = "רשום נקודות לימוד מהפרשה השבועית באמצע השבוע."
    else:
        system = "Ты мудрый наставник, формулирующий мысли ясно."
        prompt = "Напиши несколько пунктов: чему нас учит текущая недельная глава Торы."
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_shabbat_toast(lang: str) -> str:
    if lang == "en":
        system = "You are familiar with Shabbat traditions and craft warm toasts in English."
        prompt = "Create a short, heartfelt Shabbat toast based on this week's Torah portion."
    elif lang == "he":
        system = "אתה מכיר את מסורת השבת ויוצר ברכה חמה בעברית."
        prompt = "כתוב ברכת שבת קצרה על פי הפרשה השבועית."
    else:
        system = "Ты знаешь традиции шаббата и создаешь теплые тосты."
        prompt = "Подготовь короткий теплый тост для шаббата на основе текущей недельной главы Торы."
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def broadcast_parasha(context: CallbackContext):
    for uid, lang in user_langs.items():
        text = await generate_parasha_summary(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"📖 Пересказ главы:\n{text}")

async def broadcast_reflection(context: CallbackContext):
    for uid, lang in user_langs.items():
        text = await generate_midweek_reflection(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"💡 Чему нас учит глава:\n{text}")

async def broadcast_toast(context: CallbackContext):
    for uid, lang in user_langs.items():
        text = await generate_shabbat_toast(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"🥂 Тост к шаббату:\n{text}")

def main():
    load_user_langs()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", start))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r"^lang\|"))

    # Schedule jobs using built-in job queue
    tz = ZoneInfo("Asia/Dubai")
    jq = app.job_queue
    jq.run_daily(broadcast_parasha,    time=time(hour=10, minute=0, tzinfo=tz), days=(0,))  # Monday
    jq.run_daily(broadcast_reflection, time=time(hour=10, minute=0, tzinfo=tz), days=(2,))  # Wednesday
    jq.run_daily(broadcast_toast,      time=time(hour=11, minute=0, tzinfo=tz), days=(4,))  # Friday

    app.run_polling()

if __name__ == "__main__":
    main()
