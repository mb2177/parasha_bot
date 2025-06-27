import os
import logging
import json
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# ВСТАВЬТЕ ВАШИ КЛЮЧИ:
TELEGRAM_BOT_TOKEN = "7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M"
OPENAI_API_KEY     = "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"
LANG_FILE          = "user_langs.json"
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)
# In-memory map of user_id -> lang
user_langs = {}

# Load/save user languages

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
def start(update: Update, context):
    buttons = [[
        InlineKeyboardButton('🇷🇺 Русский', callback_data='lang|ru'),
        InlineKeyboardButton('🇬🇧 English', callback_data='lang|en'),
        InlineKeyboardButton('🇮🇱 עברית', callback_data='lang|he'),
    ]]
    update.message.reply_text(
        'Выберите язык / Choose your language / בחר שפה:',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def lang_callback(update: Update, context):
    query = update.callback_query
    query.answer()
    lang = query.data.split('|')[1]
    uid = str(query.from_user.id)
    user_langs[uid] = lang
    save_user_langs()
    labels = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}
    query.edit_message_text(f'Язык установлен: {labels[lang]}')

def brief_handler(update: Update, context):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'ru')
    summary = asyncio.get_event_loop().run_until_complete(generate_parasha_summary(lang))
    update.message.reply_text(f'📖 Кратко про главу / Briefly Parshah:\n{summary}')

def full_handler(update: Update, context):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'ru')
    full = asyncio.get_event_loop().run_until_complete(generate_parasha_full_text(lang))
    for i in range(0, len(full), 4000):
        update.message.reply_text(full[i:i+4000])
    if len(full) > 4000:
        update.message.reply_text('✅ Текст был длинным, разбит на несколько сообщений.')

# --- OpenAI generation ---
async def generate_parasha_summary(lang: str) -> str:
    # ... same logic as before
    if lang == 'en':
        sys, prm = (
            "You are an expert on the Torah, explaining simply in English.",
            "Write a simple summary of this week's Torah portion."
        )
    elif lang == 'he':
        sys, prm = (
            "אתה מומחה לתורה ומסביר בפשטות בעברית.",
            "כתוב תקציר פשוט של הפרשה השבועית."
        )
    else:
        sys, prm = (
            "Ты эксперт по еврейским текстам, объясняй простым языком.",
            "Напиши простой пересказ недельной главы Торы."
        )
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':sys},{'role':'user','content':prm}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_parasha_full_text(lang: str) -> str:
    if lang == 'en':
        sys = "Provide full text of this week's Torah portion in English."
        prm = "Full text of this week's Torah portion."
    elif lang == 'he':
        sys = "כתוב את הטקסט המלא של הפרשה השבועית בעברית."
        prm = sys
    else:
        sys = "Предоставь полный текст недельной главы Торы на русском языке."
        prm = sys
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':sys},{'role':'user','content':prm}],
        temperature=0.5,
        max_tokens=4096
    )
    return resp.choices[0].message.content.strip()

# --- Schedule jobs ---
def schedule_jobs(job_queue):
    tz = ZoneInfo('Asia/Dubai')
    job_queue.run_daily(lambda c: c.application.bot.send_message(chat_id=int(uid), text=f"📖 Кратко про главу / Briefly Parshah:\n{asyncio.get_event_loop().run_until_complete(generate_parasha_summary(lang))}"),
                        time=time(12,20,tzinfo=tz), days=(0,2,4))

# --- Main ---
def main():
    load_user_langs()
    app = ApplicationBuilder()\
        .token(TELEGRAM_BOT_TOKEN)\
        .post_init(lambda app: app.bot.set_my_commands([
            BotCommand('start','Начать/Restart'),
            BotCommand('language','Сменить язык'),
            BotCommand('brief','Briefly Parshah'),
            BotCommand('full','Full Parshah'),
        ]))\
        .build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))

    schedule_jobs(app.job_queue)
    app.run_polling()

if __name__ == '__main__':
    main()
