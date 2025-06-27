#!/usr/bin/env python3
import os
import logging
import json
import asyncio
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Попытка применить nest_asyncio для избежания ошибок event loop в интерактивной среде
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# -----------------------------------------------------------------------------
# Конфигурация: вставьте свои ключи (в кавычках или через переменные окружения)
TELEGRAM_BOT_TOKEN = os.getenv('7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M')
OPENAI_API_KEY     = os.getenv('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')
USER_LANG_FILE     = 'user_langs.json'
MESSAGE_LOG_FILE   = 'message_logs.json'
# -----------------------------------------------------------------------------

# Логирование
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Хранилища
user_langs   = {}
message_logs = {}

# --- Вспомогательные функции для загрузки/сохранения данных ---
def load_user_langs():
    global user_langs
    try:
        with open(USER_LANG_FILE, 'r', encoding='utf-8') as f:
            user_langs = json.load(f)
    except FileNotFoundError:
        user_langs = {}

def save_user_langs():
    with open(USER_LANG_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f, ensure_ascii=False, indent=2)

def load_message_logs():
    global message_logs
    try:
        with open(MESSAGE_LOG_FILE, 'r', encoding='utf-8') as f:
            message_logs = json.load(f)
    except FileNotFoundError:
        message_logs = {}

def save_message_logs():
    with open(MESSAGE_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(message_logs, f, ensure_ascii=False, indent=2)

def log_message(user_id: str, text: str, msg_type: str):
    """Записать историю сообщений для пользователя."""
    entry = {
        'timestamp': datetime.now(ZoneInfo('Asia/Dubai')).isoformat(),
        'type': msg_type,
        'text': text
    }
    message_logs.setdefault(user_id, []).append(entry)
    save_message_logs()

# --- Локализованные тексты интерфейса ---
TEXTS = {
    'ru': {
        'language_prompt': 'Выберите язык:',
        'language_set'   : 'Язык установлен: {label}',
        'menu'           : 'Выберите действие:',
        'summary_prefix' : '📖 Кратко про главу:\n',
        'full_prefix'    : '📜 Полная глава:\n',
        'error'          : '⚠️ Произошла ошибка. Попробуйте позже.'
    },
    'en': {
        'language_prompt': 'Choose your language:',
        'language_set'   : 'Language set to: {label}',
        'menu'           : 'Choose an action:',
        'summary_prefix' : '📖 Briefly Parshah:\n',
        'full_prefix'    : '📜 Full Parshah:\n',
        'error'          : '⚠️ An error occurred. Please try again later.'
    },
    'he': {
        'language_prompt': 'בחר שפה:',
        'language_set'   : 'השפה הוגדרה ל: {label}',
        'menu'           : 'בחר פעולה:',
        'summary_prefix' : '📖 תקציר פרשה:\n',
        'full_prefix'    : '📜 הפרשה המלאה:\n',
        'error'          : '⚠️ אירעה שגיאה. אנא נסה שוב מאוחר יותר.'
    }
}

LANG_LABELS = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}

def get_text(key: str, lang: str, **kwargs) -> str:
    return TEXTS.get(lang, TEXTS['en'])[key].format(**kwargs)

# --- Функции генерации через OpenAI ---
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
            {'role': 'system', 'content': sys_map.get(lang, sys_map['en'])},
            {'role': 'user', 'content': prompt_map.get(lang, prompt_map['en'])},
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
            {'role': 'system', 'content': text_map.get(lang, text_map['en'])},
            {'role': 'user', 'content': text_map.get(lang, text_map['en'])},
        ],
        temperature=0.5,
        max_tokens=4096,
    )
    return resp.choices[0].message.content.strip()

# --- Обработчики команд и кнопок ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start и /language — выбор языка."""
    keyboard = [
        [InlineKeyboardButton(LANG_LABELS['ru'], callback_data='lang|ru')],
        [InlineKeyboardButton(LANG_LABELS['en'], callback_data='lang|en')],
        [InlineKeyboardButton(LANG_LABELS['he'], callback_data='lang|he')],
    ]
    await update.message.reply_text(
        get_text('language_prompt', 'en'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора языка."""
    query = update.callback_query
    await query.answer()
    lang = query.data.split('|', 1)[1]
    user_id = str(query.from_user.id)
    user_langs[user_id] = lang
    save_user_langs()

    # Подтверждение языка
    await query.edit_message_text(get_text('language_set', lang, label=LANG_LABELS[lang]))

    # Показать главное меню кнопок
    menu_buttons = [
        [KeyboardButton("📚 Кратко про главу"), KeyboardButton("📜 Полная глава")],
        [KeyboardButton("/language")]
    ]
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=get_text('menu', lang),
        reply_markup=ReplyKeyboardMarkup(menu_buttons, resize_keyboard=True)
    )

async def brief_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = user_langs.get(user_id, 'en')
    try:
        summary = await generate_summary(lang)
        text = get_text('summary_prefix', lang) + summary
        await update.message.reply_text(text)
        log_message(user_id, text, 'manual')
    except Exception as e:
        logger.error(f"Error in brief_handler: {e}")
        await update.message.reply_text(get_text('error', lang))

async def full_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = user_langs.get(user_id, 'en')
    try:
        full = await generate_full_text(lang)
        prefix = get_text('full_prefix', lang)
        chunks = [full[i:i+4000] for i in range(0, len(full), 4000)]
        for idx, chunk in enumerate(chunks):
            text = prefix + chunk if idx == 0 else chunk
            await update.message.reply_text(text)
        if len(chunks) > 1:
            await update.message.reply_text('✅ Текст был длинным и разбит на несколько сообщений')
        log_message(user_id, prefix + full, 'manual')
    except Exception as e:
        logger.error(f"Error in full_handler: {e}")
        await update.message.reply_text(get_text('error', lang))

async def broadcast_summary(context: ContextTypes.DEFAULT_TYPE):
    """Рассылка ежедневного краткого пересказа."""
    for user_id, lang in user_langs.items():
        try:
            summary = await generate_summary(lang)
            text = get_text('summary_prefix', lang) + summary
            await context.bot.send_message(chat_id=int(user_id), text=text)
            log_message(user_id, text, 'auto')
        except Exception as e:
            logger.error(f"Error broadcasting to {user_id}: {e}")

def schedule_jobs(job_queue):
    tz = ZoneInfo('Asia/Dubai')
    # Ежедневно в 12:20 по времени Дубая
    job_queue.run_daily(broadcast_summary, time=time(12, 20, tzinfo=tz))

async def main():
    load_user_langs()
    load_message_logs()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(
        lambda a: a.bot.set_my_commands([
            BotCommand('start', 'Start bot'),
            BotCommand('language', 'Change language'),
            BotCommand('brief', 'Briefly Parshah'),
            BotCommand('full', 'Full Parshah'),
        ])
    ).build()

    # Регистрация хендлеров
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(MessageHandler(filters.TEXT("📚 Кратко про главу"), brief_handler))
    app.add_handler(MessageHandler(filters.TEXT("📜 Полная глава"), full_handler))

    schedule_jobs(app.job_queue)

    # Запуск бота
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
