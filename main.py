"""
Telegram-бот с чатом на базе Google Gemini API.
Помнит историю диалога для каждого пользователя (пока бот запущен).

Автор: сгенерировано на ~40% с помощью Claude
"""

import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

GEMINI_API_KEYS = [
    v for v in (
        os.environ.get("GEMINI_API_KEY_1"),
        os.environ.get("GEMINI_API_KEY_2"),
        os.environ.get("GEMINI_API_KEY_3"),
    ) if v
]

if not GEMINI_API_KEYS:
    raise RuntimeError("Не задано ни одного GEMINI_API_KEY_1/2/3 в переменных окружения")

_current_key_index = 0

SYSTEM_PROMPT = (
    "Ты дружелюбный и полезный ассистент в Telegram-боте. "
    "Отвечай понятно, по делу, без лишней воды."
)

MODEL_NAME = "gemini-1.5-flash"
MAX_HISTORY_MESSAGES = 20

user_histories: dict[int, list] = {}


def get_model():
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
    )


async def ask_gemini(user_id: int, user_message: str) -> str:
    global _current_key_index
    history = user_histories.get(user_id, [])

    last_error = None
    for attempt in range(len(GEMINI_API_KEYS)):
        key_index = (_current_key_index + attempt) % len(GEMINI_API_KEYS)
        try:
            genai.configure(api_key=GEMINI_API_KEYS[key_index])
            model = get_model()
            chat = model.start_chat(history=history)
            response = chat.send_message(user_message)

            _current_key_index = key_index
            user_histories[user_id] = chat.history[-MAX_HISTORY_MESSAGES:]
            return response.text

        except Exception as e:
            last_error = e
            logger.warning(f"Ключ #{key_index + 1} не сработал: {e}. Пробуем следующий...")
            continue

    raise last_error


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text(
        "Привет! Я бот на базе Gemini. Просто пиши сообщение — отвечу.\n\n"
        "Команды:\n"
        "/reset — очистить историю диалога"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("История диалога очищена. Начинаем заново!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        reply = await ask_gemini(user_id, user_text)
    except Exception as e:
        logger.error(f"Ошибка запроса к Gemini: {e}")
        reply = "Извини, что-то пошло не так. Попробуй ещё раз чуть позже."

    await update.message.reply_text(reply)


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
