from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "ТВОЙ_ТОКЕН_БОТА"
APP_URL = "https://otar989.github.io/bugman-miniapp-/"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(text="🎮 Играть", url=APP_URL)]]
    await update.message.reply_text(
        text="👋 Привет! Добро пожаловать в Bugman!\n\nНажми кнопку ниже, чтобы запустить игру:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()