import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

current_bankroll = 120.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Athena 13 Betting Engine Active!\nCommands:\n/bankroll [amount]\n/predict [Team]")

async def update_bankroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_bankroll
    try:
        new_val = float(context.args[0])
        current_bankroll = new_val
        await update.message.reply_text(f"✅ Bankroll updated: €{current_bankroll}")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /bankroll 135")

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    team_name = " ".join(context.args)
    if not team_name:
        await update.message.reply_text("⚠️ Usage: /predict [Team Name]")
        return
    stake = round(current_bankroll * 0.03, 2)
    await update.message.reply_text(f"📊 [Athena 13] Match: {team_name}\nRecommended Stake: €{stake}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bankroll", update_bankroll))
    app.add_handler(CommandHandler("predict", predict))
    app.run_polling()

if __name__ == '__main__':
    main()
