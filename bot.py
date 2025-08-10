import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ["TOKEN"]  # токен бота из переменных окружения
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🎮 Играть", url=APP_URL)]]
    await update.message.reply_text(
        "👾 Привет! Добро пожаловать в Bugman!\n\nЖми кнопку ниже, чтобы запустить игру:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling(close_loop=False)
