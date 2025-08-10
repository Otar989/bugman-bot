import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ["TOKEN"]
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # КНОПКА WEB APP (откроется внутри Telegram)
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    await update.message.reply_text(
        "👾 Привет! Добро пожаловать в Bugman!\n\nЖми кнопку ниже — игра откроется внутри Telegram:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling(close_loop=False)
