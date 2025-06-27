import os
import logging
import json
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# Вставьте сюда свои ключи (в строковых кавычках)
TELEGRAM_BOT_TOKEN = "7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M"
OPENAI_API_KEY     = "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"
LANG_FILE          = "user_langs.json"
# ──────────────────────────────────────────────────────────────────────────────

# Логирование
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
# Клиент OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)
# Память языков пользователей
user_langs = {}

# --- Загрузка/сохранение языков ---
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

# --- Обработчики команд ---
def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton('🇷🇺 Русский', callback_data='lang|ru'),
        InlineKeyboardButton('🇬🇧 English', callback_data='lang|en'),
        InlineKeyboardButton('🇮🇱 עברית', callback_data='lang|he'),
    ]]
    update.message.reply_text(
        'Выберите язык / Choose your language / בחר שפה:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split('|')[1]
    uid = str(query.from_user.id)
    user_langs[uid] = lang
    save_user_langs()
    labels = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}
    await query.edit_message_text(f'Язык установлен: {labels[lang]}')

# Общая функция отправки контента
async def send_parasha(update: Update, context: ContextTypes.DEFAULT_TYPE, brief: bool):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'ru')
    if brief:
        text = await generate_summary(lang)
        header = '📖 Кратко про главу / Briefly Parshah'
    else:
        text = await generate_full(lang)
        header = '📜 Полная глава / Full Parshah'
    # Если вызывается через callback_query
    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message
    # Разбивка на части по 4000 символов
    for i in range(0, len(text), 4000):
        await target.reply_text(f"{header}:\n{text[i:i+4000]}")
    if len(text) > 4000:
        await target.reply_text('✅ Текст был слишком длинным и разбит на несколько сообщений')

# Адаптеры для команд
def brief_handler(update, context):
    return context.application.create_task(send_parasha(update, context, brief=True))

def full_handler(update, context):
    return context.application.create_task(send_parasha(update, context, brief=False))

# --- Генерация через OpenAI ---
async def generate_summary(lang: str) -> str:
    if lang == 'en':
        system = 'You are an expert on the Torah, explaining its weekly portion simply in English.'
        prompt = "Write a simple summary of this week's Torah portion."
    elif lang == 'he':
        system = 'אתה מומחה לתורה ומסביר את הפרשה השבועית בפשטות בעברית.'
        prompt = 'כתוב תקציר פשוט של הפרשה השבועית.'
    else:
        system = 'Ты эксперт по еврейским текстам и объясняешь простым языком.'
        prompt = 'Напиши простой пересказ недельной главы Торы.'
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':system},{'role':'user','content':prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_full(lang: str) -> str:
    if lang == 'en':
        system = 'Provide the full text of this week\'s Torah portion in English.'
        prompt = system
    elif lang == 'he':
        system = 'כתוב את הטקסט המלא של הפרשה השבועית בעברית.'
        prompt = system
    else:
        system = 'Предоставь полный текст недельной главы Торы на русском языке.'
        prompt = system
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':system},{'role':'user','content':prompt}],
        temperature=0.5,
        max_tokens=4096
    )
    return resp.choices[0].message.content.strip()

# --- Автоматическая рассылка ---
def schedule_jobs(job_queue):
    tz = ZoneInfo('Asia/Dubai')
    # Понедельник: краткий пересказ
    job_queue.run_daily(lambda ctx: ctx.application.create_task(broadcast_summary(ctx)), time=time(12,20,tzinfo=tz), days=(0,))
    # Среда: рефлексия. Тут можно добавить свою функцию broadcast_reflection
    # Пятница: тост. Можно тоже добавить broadcast_toast

def broadcast_summary(context):
    for uid, lang in user_langs.items():
        context.application.create_task(
            context.bot.send_message(chat_id=int(uid), text=f"📖 Кратко про главу / Briefly Parshah:\n{await generate_summary(lang)}")
        )

# --- Основной запуск ---
def main():
    load_user_langs()
    app = ApplicationBuilder()\
        .token(TELEGRAM_BOT_TOKEN)\
        .post_init(lambda a: a.bot.set_my_commands([
            BotCommand('start','Начать или перезапустить'),
            BotCommand('language','Сменить язык'),
            BotCommand('brief','Кратко про главу / Briefly Parshah'),
            BotCommand('full','Полная глава / Full Parshah'),
        ]))\
        .build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))

    # Планирование
    schedule_jobs(app.job_queue)

    # Запуск long-polling
    app.run_polling()

if __name__ == '__main__':
    main()
