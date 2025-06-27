import os
import logging
import json
import asyncio
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# ВСТАВЬТЕ СВОИ КЛЮЧИ В КАВЫЧКАХ:
TELEGRAM_BOT_TOKEN = "7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M"
OPENAI_API_KEY     = "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"
LANG_FILE          = "user_langs.json"
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
user_langs = {}

# --- Загрузка и сохранение языковых настроек ---
def load_user_langs():
    global user_langs
    try:
        with open(LANG_FILE, 'r', encoding='utf-8') as f:
            user_langs = json.load(f)
    except FileNotFoundError:
        user_langs = {}

def save_user_langs():
    with open(LANG_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f, ensure_ascii=False, indent=2)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [
            InlineKeyboardButton('🇷🇺 Русский', callback_data='lang|ru'),
            InlineKeyboardButton('🇬🇧 English', callback_data='lang|en'),
            InlineKeyboardButton('🇮🇱 עברית', callback_data='lang|he'),
        ]
    ]
    await update.message.reply_text(
        'Выберите язык / Choose your language / בחר שפה:',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    lang = update.callback_query.data.split('|')[1]
    uid = str(update.effective_user.id)
    user_langs[uid] = lang
    save_user_langs()
    labels = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}
    await update.callback_query.edit_message_text(f'Язык установлен: {labels[lang]}')

async def brief_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_parasha(update, context, brief=True)

async def full_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_parasha(update, context, brief=False)

async def _send_parasha(update: Update, context: ContextTypes.DEFAULT_TYPE, brief: bool):
    if update.callback_query:
        await update.callback_query.answer()
        uid = str(update.callback_query.from_user.id)
        target = update.callback_query.message
    else:
        uid = str(update.effective_user.id)
        target = update.message
    lang = user_langs.get(uid, 'ru')
    if brief:
        text = await generate_parasha_summary(lang)
        title = '📖 Кратко про главу / Briefly Parshah'
    else:
        full = await generate_parasha_full_text(lang)
        parts = [full[i:i+4000] for i in range(0, len(full), 4000)]
        for part in parts:
            await target.reply_text(part)
        if len(parts) > 1:
            await target.reply_text('✅ Текст был длинным, разбит на несколько сообщений.')
        return
    await target.reply_text(f"{title}:\n{text}")

# --- OpenAI generation ---
async def generate_parasha_summary(lang: str) -> str:
    if lang == 'en':
        system = 'You are an expert on the Torah, explaining its weekly portion simply in English.'
        prompt = "Write a simple summary of this week's Torah portion for those unfamiliar with religious texts."
    elif lang == 'he':
        system = 'אתה מומחה לתורה ומסביר את הפרשה השבועית בפשטות בעברית.'
        prompt = 'כתוב תקציר פשוט של הפרשה השבועית עבור מי שלא מכיר טקסטים דתיים.'
    else:
        system = 'Ты эксперт по еврейским текстам и умеешь объяснять их простым языком.'
        prompt = 'Напиши простым языком краткий пересказ текущей недельной главы Торы.'
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':system},{'role':'user','content':prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_parasha_full_text(lang: str) -> str:
    if lang == 'en':
        system = 'You have access to the full text of the weekly Torah portion. Provide the complete text in English.'
        prompt = "Provide the full text of this week's Torah portion in English."
    elif lang == 'he':
        system = 'אתה בעל גישה מלאה לטקסט מלא של הפרשה השבועית. הצג את הטקסט המלא בעברית.'
        prompt = 'כתוב את הטקסט המלא של הפרשה השבועית בעברית.'
    else:
        system = 'Ты обладаешь полным текстом недельной главы Торы. Предоставь полный текст на русском языке.'
        prompt = 'Напиши полный текст текущей недельной главы Торы на русском языке.'
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':system},{'role':'user','content':prompt}],
        temperature=0.5,
        max_tokens=4096
    )
    return resp.choices[0].message.content.strip()

# --- Schedule jobs ---
def schedule_jobs(app):
    tz = ZoneInfo('Asia/Dubai')
    jq = app.job_queue
    jq.run_daily(lambda ctx: asyncio.create_task(broadcast_summary(ctx)), time=time(12,20,tzinfo=tz), days=(0,))
    jq.run_daily(lambda ctx: asyncio.create_task(broadcast_reflection(ctx)), time=time(12,20,tzinfo=tz), days=(2,))
    jq.run_daily(lambda ctx: asyncio.create_task(broadcast_toast(ctx)), time=time(12,20,tzinfo=tz), days=(4,))

async def broadcast_summary(context: ContextTypes.DEFAULT_TYPE):
    for uid, lang in user_langs.items():
        text = await generate_parasha_summary(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"📖 Кратко про главу / Briefly Parshah:\n{text}")

async def broadcast_reflection(context: ContextTypes.DEFAULT_TYPE):
    for uid, lang in user_langs.items():
        text = await generate_midweek_reflection(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"💡 Чему нас учит глава:\n{text}")

async def broadcast_toast(context: ContextTypes.DEFAULT_TYPE):
    for uid, lang in user_langs.items():
        text = await generate_shabbat_toast(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"🥂 Тост к шаббату:\n{text}")

# --- Main ---
async def main():
    load_user_langs()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register slash commands
    await app.bot.set_my_commands([
        BotCommand('start', 'Начать или перезапустить'),
        BotCommand('language', 'Сменить язык'),
        BotCommand('brief', 'Кратко про главу / Briefly Parshah'),
        BotCommand('full', 'Полная глава / Full Parshah'),
    ])

    # Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))

    schedule_jobs(app)
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
