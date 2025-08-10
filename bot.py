import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Secrets/URLs
TOKEN = os.environ["TOKEN"]  # set this in Render → Environment Variables
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")
MEDIA_URL = "https://github.com/Otar989/bugman-bot/blob/main/bugman.gif?raw=true"  # your GIF

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # One message: GIF (animation) + caption + WebApp button
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    markup = InlineKeyboardMarkup(kb)
    caption = "👾 Привет! Добро пожаловать в Bugman!\n\nЖми «Играть» — Mini App откроется внутри Telegram."

    try:
        await update.message.reply_animation(animation=MEDIA_URL, caption=caption, reply_markup=markup)
    except Exception:
        # fallback in case Telegram can't treat the file as animation
        await update.message.reply_photo(photo=MEDIA_URL, caption=caption, reply_markup=markup)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    logging.info("Bot started. Waiting for /start …")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
