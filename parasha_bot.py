import os
import logging
import json
from datetime import time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from openai import OpenAI

# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация: вставьте свои ключи в кавычках
TELEGRAM_BOT_TOKEN = "7959503859:AAGaokGubdGPHRSivp6n11R7gNwuywX7Q-M"
OPENAI_API_KEY     = "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"
LANG_FILE          = "user_langs.json"
# ──────────────────────────────────────────────────────────────────────────────

# Логирование
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Инициализация OpenAI клиента
openai_client = OpenAI(api_key=OPENAI_API_KEY)
# Память языковых настроек пользователей
user_langs = {}

# Функции для загрузки/сохранения языков

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
async def start(update: Update, context):
    buttons = [[
        InlineKeyboardButton('🇷🇺 Russian', callback_data='lang|ru'),
        InlineKeyboardButton('🇬🇧 English', callback_data='lang|en'),
        InlineKeyboardButton('🇮🇱 עברית', callback_data='lang|he'),
    ]]
    await update.message.reply_text(
        'Choose your language / בחר שפה / Выберите язык:',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def lang_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang = query.data.split('|',1)[1]
    uid = str(query.from_user.id)
    user_langs[uid] = lang
    save_user_langs()
    labels = {'ru': '🇷🇺 Russian', 'en': '🇬🇧 English', 'he': '🇮🇱 עברית'}
    await query.edit_message_text(f'Language set: {labels[lang]}')

async def brief_handler(update: Update, context):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'en')
    text = await generate_summary(lang)
    await update.message.reply_text(f"📖 Briefly Parshah ({lang}):\n{text}")

async def full_handler(update: Update, context):
    uid = str(update.effective_user.id)
    lang = user_langs.get(uid, 'en')
    full = await generate_full_text(lang)
    for i in range(0, len(full), 4000):
        await update.message.reply_text(full[i:i+4000])
    if len(full) > 4000:
        await update.message.reply_text("✅ Full text was long and split into multiple messages.")

# --- Генерация через OpenAI ---
async def generate_summary(lang: str) -> str:
    sys_map = {
        'ru': "Ты эксперт по Торе, кратко перескажи текущую главу простым языком.",
        'en': "You are an expert on the Torah, give a simple summary of this week's portion.",
        'he': "אתה מומחה לתורה, כתוב סקירה קצרה של הפרשה בשפה פשוטה."
    }
    prompt_map = {
        'ru': "Напиши простой краткий пересказ этой недельной главы Торы.",
        'en': "Write a simple summary of this week's Torah portion.",
        'he': "כתוב תקציר פשוט של הפרשה השבועית."
    }
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role':'system','content':sys_map[lang]},
            {'role':'user','content':prompt_map[lang]}
        ],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

async def generate_full_text(lang: str) -> str:
    text_map = {
        'ru': "Предоставь полный текст текущей недельной главы Торы на русском языке.",
        'en': "Provide the full text of this week's Torah portion in English.",
        'he': "כתוב את הטקסט המלא של הפרשה השבועית בעברית."
    }
    resp = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role':'system','content':text_map[lang]},{'role':'user','content':text_map[lang]}],
        temperature=0.5,
        max_tokens=4096
    )
    return resp.choices[0].message.content.strip()

# --- Автоматическая рассылка ---
def schedule_jobs(job_queue):
    tz = ZoneInfo('Asia/Dubai')
    # Monday: weekly summary
    job_queue.run_daily(broadcast_summary, time=time(12,20,tzinfo=tz), days=(0,))
    # Wednesday: midweek reflection
    job_queue.run_daily(broadcast_reflection, time=time(12,20,tzinfo=tz), days=(2,))
    # Friday: Shabbat toast
    job_queue.run_daily(broadcast_toast, time=time(12,20,tzinfo=tz), days=(4,))

async def broadcast_summary(context):
    for uid, lang in user_langs.items():
        text = await generate_summary(lang)
        await context.bot.send_message(chat_id=int(uid), text=f"📖 Briefly Parshah ({lang}):\n{text}")

async def broadcast_reflection(context):
    for uid, lang in user_langs.items():
        prompts = {
            'ru': "Напиши несколько ключевых мыслей из текущей главы Торы.",
            'en': "List key reflection points from this week's Torah portion.",
            'he': "רשום נקודות למחשבה מהפרשה השבועית."
        }
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role':'system','content':prompts[lang]},{'role':'user','content':prompts[lang]}],
            temperature=0.7
        )
        text = resp.choices[0].message.content.strip()
        await context.bot.send_message(chat_id=int(uid), text=f"💡 Reflection ({lang}):\n{text}")

async def broadcast_toast(context):
    for uid, lang in user_langs.items():
        prompts = {
            'ru': "Напиши теплый тост к шаббату по текущей главе Торы.",
            'en': "Create a warm Shabbat toast based on this week's Torah portion.",
            'he': "כתוב ברכת שבת חמה על פי הפרשה השבועית."
        }
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role':'system','content':prompts[lang]},{'role':'user','content':prompts[lang]}],
            temperature=0.7
        )
        text = resp.choices[0].message.content.strip()
        await context.bot.send_message(chat_id=int(uid), text=f"🥂 Shabbat Toast ({lang}):\n{text}")

# --- Основная функция ---
def main():
    load_user_langs()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрация slash-команд
    app.bot.create_task(app.bot.set_my_commands([
        BotCommand('start', 'Начать или перезапустить'),
        BotCommand('language', 'Сменить язык'),
        BotCommand('brief', 'Briefly Parshah'),
        BotCommand('full', 'Full Parshah'),
    ]))

    # Регистрация обработчиков
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('language', start))
    app.add_handler(CommandHandler('brief', brief_handler))
    app.add_handler(CommandHandler('full', full_handler))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r'^lang\|'))

    # Планирование задач
    schedule_jobs(app.job_queue)

    # Запуск long-polling
    app.run_polling()

if __name__ == '__main__':
    main()
