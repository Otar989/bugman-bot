import os
import asyncio
import logging

from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- Логи ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bugman")

# ---------- Конфиг ----------
# В Render добавь переменные окружения: TOKEN (обяз.), APP_URL (опц.), MEDIA_URL (опц.)
TOKEN = os.environ["TOKEN"]
APP_URL = os.environ.get("APP_URL", "https://otar989.github.io/bugman-miniapp-/")
MEDIA_URL = os.environ.get(
    "MEDIA_URL",
    "https://github.com/Otar989/bugman-bot/blob/main/bugman.gif?raw=true",
)

# ---------- Telegram-handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=APP_URL))]]
    markup = InlineKeyboardMarkup(kb)
    caption = (
        "👾 Привет! Добро пожаловать в Bugman!\n\n"
        "Жми «Играть» — Mini App откроется внутри Telegram."
    )

    chat_id = update.effective_chat.id
    message = update.effective_message

    # Пытаемся как GIF, если не выйдет — как фото (например, в десктоп-клиенте)
    try:
        if message:
            await message.reply_animation(animation=MEDIA_URL, caption=caption, reply_markup=markup)
        else:
            await context.bot.send_animation(chat_id=chat_id, animation=MEDIA_URL, caption=caption, reply_markup=markup)
    except Exception:
        try:
            if message:
                await message.reply_photo(photo=MEDIA_URL, caption=caption, reply_markup=markup)
            else:
                await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_URL, caption=caption, reply_markup=markup)
        except Exception:
            # Если отправка медиа не удалась, хотя бы приветствуем текстом
            if message:
                await message.reply_text(text=caption, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=markup)

# ---------- Aiohttp health ----------
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Bugman bot is running ✅")

# ---------- Асинхронный main: бот + веб-сервер в одном event loop ----------
async def main():
    # --- Telegram Application ---
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Инициализируем и запускаем бота (polling) без run_polling, чтобы управлять циклом сами
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    log.info("Telegram bot polling started")

    # --- Aiohttp server (для Render) ---
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info(f"Health endpoint started on 0.0.0.0:{port}")

    # Держим процесс живым
    try:
        await asyncio.Event().wait()
    finally:
        # Корректная остановка
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    # Один event loop, без потоков — надёжно для Python 3.13/asyncio
    asyncio.run(main())
