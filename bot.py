import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ["TOKEN"]

# Ссылка на Mini App внутри Telegram
APP_URL = "https://t.me/bugman_bot/myapp"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Кнопка, открывающая Mini App внутри Telegram
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    await update.message.reply_text(
        "👾 Привет! Добро пожаловать в Bugman!\n\nЖми кнопку ниже, чтобы играть прямо в Telegram:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling(close_loop=False)
