import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Read secrets from environment
TOKEN = os.environ["TOKEN"]  # set in Render → Environment Variables
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")  # your MiniApp URL

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # WebApp button opens inside Telegram
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    await update.message.reply_text(
        "👾 Привет! Добро пожаловать в Bugman!\n\nЖми «Играть» — Mini App откроется внутри Telegram.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    logging.info("Bot started. Waiting for /start …")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
