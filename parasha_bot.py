import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI
import asyncio

# Загрузка токенов из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Доступные языки
LANGS = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "he": "🇮🇱 עברית"
}

# Промпты для GPT
PROMPTS = {
    "summary": {
        "ru": "Кратко перескажи недельную главу Торы на этой неделе. Просто, понятно и интересно. Начни с названия главы. В конце добавь комментарий на русском.",
        "en": "Briefly summarize this week's Torah portion in a simple, clear, and engaging way. Add a short comment in English at the end.",
        "he": "סכם בקצרה את פרשת השבוע בצורה פשוטה וברורה. הוסף תגובה קצרה בסוף."
    },
    "full": {
        "ru": "Расскажи подробно, но понятно о недельной главе Торы этой недели. Начни с названия главы. В конце добавь комментарий на русском.",
        "en": "Tell the full story of this week's Torah portion in a clear and engaging way. Start with the parashah name. End with a short English comment.",
        "he": "ספר את סיפור הפרשה בצורה מלאה וברורה. התחל בשם הפרשה. סיים בתגובה קצרה בסוף."
    },
    "questions": {
        "ru": "Какие жизненные уроки можно извлечь из недельной главы Торы? Задай 1-2 вопроса, о которых стоит подумать.",
        "en": "What life lessons can be learned from this week's Torah portion? Ask 1-2 questions to reflect on.",
        "he": "אילו מסרים אפשר ללמוד מהפרשה? שאל 1-2 שאלות שמעוררות מחשב.",
    },
    "toast": {
        "ru": "Сделай короткий, мудрый, но не тяжёлый тост на Шаббат, связанный с темой недельной главы.",
        "en": "Write a short, wise but light Shabbat toast inspired by this week's Torah portion.",
        "he": "כתוב לחיים קצר, חכם אך לא כבד, לשבת בהשראת פרשת השבוע."
    }
}

GPT_SYSTEM_PROMPT = (
    "You are a Jewish mentor. Respond clearly, inspirationally, and with respect for Torah tradition."
)

LANG_FILE = "user_langs.json"
user_langs = {}
if os.path.exists(LANG_FILE):
    with open(LANG_FILE, encoding="utf-8") as f:
        user_langs = json.load(f)

def save_langs():
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(user_langs, f, ensure_ascii=False, indent=2)

def get_lang(user_id):
    return user_langs.get(str(user_id), "ru")

# GPT via openai>=1.0.0
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
async def gpt_respond(prompt_text):
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": GPT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Ошибка GPT: {e}]"

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=code)] for code, name in LANGS.items()]
    await update.message.reply_text("Выберите язык / Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    if data in LANGS:
        user_langs[user_id] = data
        save_langs()
        await query.edit_message_text(f"Язык установлен: {LANGS[data]}")
    elif data == "enough":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Хорошо, до следующей недели 👋")
    elif data.startswith("full_"):
        prompt = PROMPTS["full"][get_lang(user_id)]
        text = await gpt_respond(prompt)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(text)

async def handle_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    user_id = str(update.effective_user.id)
    lang = get_lang(user_id)
    prompt = PROMPTS[key][lang]
    text = await gpt_respond(prompt)
    await update.message.reply_text(text)

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_gpt(update, context, "summary")

async def full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_gpt(update, context, "full")

# Mass sending with inline buttons
async def send_to_all(app, key):
    for user_id, lang in user_langs.items():
        prompt = PROMPTS[key][lang]
        text = await gpt_respond(prompt)
        try:
            if key == "summary":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("\ud83d\udcdc Подробное описание", callback_data=f"full_{user_id}")],
                    [InlineKeyboardButton("\u2705 Достаточно понятно", callback_data="enough")]
                ])
                await app.bot.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard)
            else:
                await app.bot.send_message(chat_id=int(user_id), text=text)
        except Exception as e:
            logging.warning(f"Ошибка отправки {key} пользователю {user_id}: {e}")

scheduler = AsyncIOScheduler(timezone="Asia/Dubai")

def schedule_jobs(app: Application):
    scheduler.add_job(lambda: send_to_all(app, "summary"), "cron", day_of_week="sun", hour=12, minute=20)
    scheduler.add_job(lambda: send_to_all(app, "questions"), "cron", day_of_week="wed", hour=14, minute=0)
    scheduler.add_job(lambda: send_to_all(app, "toast"), "cron", day_of_week="fri", hour=16, minute=0)
    scheduler.start()

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("full", full))
    app.add_handler(CallbackQueryHandler(button))

    await app.bot.set_my_commands([
        ("start", "Приветствие и выбор языка"),
        ("language", "Сменить язык"),
        ("summary", "\ud83d\udcda Краткий пересказ главы"),
        ("full", "\ud83d\udcdc Полная глава с пояснением")
    ])

    schedule_jobs(app)
    await app.run_polling()

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "event loop is already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise e
