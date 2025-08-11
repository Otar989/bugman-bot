import os
import logging
import threading

from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- Логи ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bugman")

# ---------- Конфиг ----------
TOKEN = os.environ["TOKEN"]  # Render → Environment → TOKEN
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")
MEDIA_URL = os.environ.get(
    "MEDIA_URL",
    "https://github.com/Otar989/bugman-bot/blob/main/bugman.gif?raw=true",
)

# ---------- Telegram-handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    markup = InlineKeyboardMarkup(kb)
    caption = "👾 Привет! Добро пожаловать в Bugman!\n\nЖми «Играть» — Mini App откроется внутри Telegram."

    send_kwargs = {
        "chat_id": update.effective_chat.id,
        "caption": caption,
        "reply_markup": markup,
    }

    try:
        await context.bot.send_animation(animation=MEDIA_URL, **send_kwargs)
    except Exception:
        await context.bot.send_photo(photo=MEDIA_URL, **send_kwargs)

def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    log.info("Telegram bot polling started")
    # В отдельном потоке: не блокируем основной процесс с веб-сервером
    app.run_polling(close_loop=False)

# ---------- Мини-веб для Render ----------
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Bugman bot is running ✅")

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.router.add_get("/", health)
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Стартуем бота в фоне (поток)
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    # Поднимаем веб-сервер (держит процесс живым на Render)
    run_web()
