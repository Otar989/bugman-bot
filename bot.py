import os
import asyncio
import logging

from aiohttp import web
from telegram import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- Логи ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bugman")

# ---------- Конфиг ----------
# В Render добавь переменную окружения TOKEN (обяз.)
TOKEN = os.environ["TOKEN"]

# ---------- Telegram-handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command.

    Always sends the Bugman GIF followed by a welcome message with an
    inline button linking to the game.
    """

    chat_id = update.effective_chat.id

    # Сначала отправляем GIF. Если не получится, просто логируем ошибку.
    try:
        await context.bot.send_animation(
            chat_id=chat_id, animation=FSInputFile("bugman.gif")
        )
    except Exception:
        log.exception("Failed to send start GIF")

    # Текст сообщения в формате Markdown
    text = (
        "🤖 Привет! Это *Bugman*.\n"
        "Ты — жёлтый, они — злые, монетки — вкусные.\n\n"
        "Выживи как можно дольше и стань легендой!\n"
        "Осторожно: игра вызывает привыкание 😎\n\n"
        "🎯 Жми «Играть» и докажи, что ты главный в этом лабиринте."
    )

    # Инлайн-кнопка с ссылкой на игру
    kb = [[InlineKeyboardButton("🎮 Играть", url="https://t.me/bugman_bot/myapp")]]
    markup = InlineKeyboardMarkup(kb)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )

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
