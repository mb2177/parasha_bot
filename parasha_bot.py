import os
import logging
import json
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация: вставьте свои ключи (в кавычках)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY     = os.getenv('OPENAI_API_KEY')
LANG_FILE          = 'user_langs.json'
# ──────────────────────────────────────────────────────────────────────────────

# Логирование
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Инициализация OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)
# Память языковых настроек пользователей
user_langs = {}

# Загрузка/сохранение настроек

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
    keyboard = [
        [InlineKeyboardButton('🇷🇺 Русский', callback_data='lang|ru')],
        [InlineKeyboardButton('🇬🇧 English', callback_data='lang|en')],
        [InlineKeyboardButton('🇮🇱 עברית', callback_data='lang|he')],
    ]
    await update.message.reply_text(
        'Выберите язык / Choose your language / בחר שפה:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split('|', 1)[1]
    user_langs[str(query.from_user.id)] = lang
    save_user_langs()
    labels = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}
    await query.edit_message_text(f'Язык установлен: {labels[lang]}')

async def brief_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'en')
    summary = await generate_summary(lang)
    await update.message.reply_text(f'📖 Кратко про главу / Briefly Parshah:\n{summary}')

async def full_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'en')
    full = await generate_full_text(lang)
    for i in range(0, len(full), 4000):
        await update.message.reply_text(full[i:i+4000])
    if len(full) > 4000:
        await update.message.reply_text('✅ Текст был длинным и разбит на несколько сообщений')

# --- OpenAI generation ---
async def generate_summary(lang: str) -> str:
    sys_map = {
        'ru': 'Ты эксперт по Торе, кратко перескажи текущую главу простым языком.',
        'en': 'You are an expert on the Torah; give a simple summary of this week’s portion.',
        'he': 'אתה מומחה לתורה; כתוב תקציר פשוט של הפרשה השבועית.'
    }
    prompt_map = {
        'ru': 'Напиши простой краткий пересказ этой недельной главы Торы.',
        'en': 'Write a simple summary of this week’s Torah portion.',
        'he': 'כתוב תקציר קצר של הפרשה השבועית.'
    }
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 'content': sys_map[lang]},
            {'role': 'user', 'content': prompt_map[lang]},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

async def generate_full_text(lang: str) -> str:
    text_map = {
        'ru': 'Предоставь полный текст недельной главы Торы на русском языке.',
        'en': 'Provide the full text of this week’s Torah portion in English.',
        'he': 'כתוב את הטקסט המלא של הפרשה השבועית בעברית.'
    }
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 'content': text_map[lang]},
            {'role': 'user', 'content': text_map[lang]},
        ],
        temperature=0.5,
        max_tokens=4096,
    )
    return resp.choices[0].message.content.strip()

# --- Scheduled broadcasts ---
def schedule_jobs(job_queue):
    tz = ZoneInfo('Asia/Dubai')
    job_queue.run_daily(broadcast_summary, time=time(12, 20, tzinfo=tz), days=(0,))
    job_queue.run_daily(broadcast_reflection, time=time(12, 20, tzinfo=tz), days=(2,))
    job_queue.run_daily(broadcast_toast, time=time(12, 20, tzinfo=tz), days=(4,))

async def broadcast_summary(context: ContextTypes.DEFAULT_TYPE):
    for uid, lang in user_langs.items():
        text = await generate_summary(lang)
        await context.bot.send_message(chat_id=int(uid), text=f'📖 Briefly Parshah ({lang}):\n{text}')

async def broadcast_reflection(context: ContextTypes.DEFAULT_TYPE):
    prompts = {
        'ru': 'Напиши несколько ключевых мыслей из текущей главы Торы.',
        'en': 'List key reflection points from this week’s Torah portion.',
        'he': 'רשום נקודות למחשבה מהפרשה השבועית.'
    }
    for uid, lang in user_langs.items():
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role':'system','content':prompts[lang]},{'role':'user','content':prompts[lang]}],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        await context.bot.send_message(chat_id=int(uid), text=f'💡 Reflection ({lang}):\n{text}')

async def broadcast_toast(context: ContextTypes.DEFAULT_TYPE):
    prompts = {
        'ru': 'Напиши теплый тост к шаббату по текущей главе Торы.',
        'en': 'Create a warm Shabbat toast based on this week’s Torah portion.',
        'he': 'כתוב ברכת שבת חמה על פי הפרשה השבועית.'
    }
    for uid, lang in user_langs.items():
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role':'system','content':prompts[lang]},{'role':'user','content':prompts[lang]}],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        await context.bot.send_message(chat_id=int(uid), text=f'🥂 Shabbat Toast ({lang}):\n{text}')

# --- Main ---
def main():
    load_user_langs()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(
        lambda a: a.bot.set_my_commands([
            BotCommand('start','Start/restart bot'),
            BotCommand('language','Change language'),
            BotCommand('brief','Briefly Parshah'),
            BotCommand('full','Full Parshah'),
        ])
    ).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))

    schedule_jobs(app.job_queue)
    app.run_polling()

if __name__ == '__main__':
    main()
