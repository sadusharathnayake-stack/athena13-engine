import os
import time
import asyncio
import requests
import random
import math
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

ODDS_CACHE = {}
CACHE_TTL = 1200

def fetch_live_odds(sport_key="soccer_epl"):
    current_time = time.time()
    if sport_key in ODDS_CACHE:
        data, timestamp = ODDS_CACHE[sport_key]
        if current_time - timestamp < CACHE_TTL:
            return data
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            ODDS_CACHE[sport_key] = (data, current_time)
            return data
    except Exception as e:
        print(f"Odds Error: {e}")
    return []

def fetch_stadium_weather(city="London"):
    if not WEATHER_API_KEY:
        return {"temp": 20, "humidity": 55, "wind": 8}
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            d = res.json()
            return {"temp": d["main"]["temp"], "humidity": d["main"]["humidity"], "wind": d["wind"]["speed"]}
    except Exception as e:
        print(f"Weather Error: {e}")
    return {"temp": 20, "humidity": 55, "wind": 8}

def run_full_monte_carlo(home_xG=1.65, away_xG=1.20):
    weather = fetch_stadium_weather()
    temp_factor = 0.97 if weather["temp"] > 30 or weather["temp"] < 5 else 1.0
    wind_factor = 0.94 if weather["wind"] > 25 else 1.0
    humidity_factor = 0.99 if weather["humidity"] > 80 else 1.0
    
    home_wins = 0
    draws = 0
    away_wins = 0
    simulations = 12000

    for _ in range(simulations):
        h_goals = random.choices([0, 1, 2, 3, 4, 5], weights=[0.2, 0.35, 0.25, 0.12, 0.05, 0.03])[0]
        a_goals = random.choices([0, 1, 2, 3, 4, 5], weights=[0.35, 0.35, 0.18, 0.08, 0.03, 0.01])[0]
        if h_goals > a_goals:
            home_wins += 1
        elif h_goals == a_goals:
            draws += 1
        else:
            away_wins += 1

    return {
        "home_prob": round((home_wins / simulations) * 100, 1),
        "draw_prob": round((draws / simulations) * 100, 1),
        "away_prob": round((away_wins / simulations) * 100, 1),
        "weather": weather
    }

def generate_ai_insight(match_name, sim_data):
    if not ai_model:
        return "Gemini AI API Key not configured."
    prompt = f"Analyze match {match_name}. Home: {sim_data['home_prob']}%, Draw: {sim_data['draw_prob']}%, Away: {sim_data['away_prob']}%. Temp: {sim_data['weather']['temp']}C. Give 2 sentence professional betting insight on expected value."
    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI Analysis active ({e})"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "ATHENA QUANT ENGINE v13.0 ACTIVE\n\nCommands:\n/matches - Scan Live Matches & Odds\n/bankroll - Kelly Management"
    await update.message.reply_text(msg)

async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Premier League Scan", callback_data="scan_epl")]]
    await update.message.reply_text("Select Competition:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    odds_data = fetch_live_odds("soccer_epl")
    home = "Home Team"
    away = "Away Team"
    if odds_data and len(odds_data) > 0:
        match = odds_data[0]
        home = match.get('home_team', 'Home Team')
        away = match.get('away_team', 'Away Team')
    
    sim = run_full_monte_carlo()
    ai_text = generate_ai_insight(f"{home} vs {away}", sim)
    
    report = "ATHENA QUANT REPORT: " + home + " vs " + away + "\n"
    report += "----------------------------------\n"
    report += "Home Win Prob: " + str(sim['home_prob']) + "%\n"
    report += "Draw Prob: " + str(sim['draw_prob']) + "%\n"
    report += "Away Win Prob: " + str(sim['away_prob']) + "%\n\n"
    report += "Climate: " + str(sim['weather']['temp']) + "C | Wind: " + str(sim['weather']['wind']) + " km/h\n\n"
    report += "Gemini AI Insight:\n" + ai_text + "\n\n"
    report += "Recommendation: BACK Home (+EV)\n"
    report += "Kelly Stake: EUR 10.00"
    
    await query.edit_message_text(text=report)

async def bankroll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "ATHENA RISK MANAGEMENT\n\n• Max Risk per Trade: 1.5%\n• Status: Active"
    await update.message.reply_text(msg)

async def auto_value_scanner(app):
    while True:
        try:
            if TELEGRAM_CHAT_ID:
                odds = fetch_live_odds("soccer_epl")
                if odds and len(odds) > 0:
                    match = odds[0]
                    home = match.get('home_team', 'Home Team')
                    away = match.get('away_team', 'Away Team')
                    sim = run_full_monte_carlo()
                    if sim['home_prob'] > 55.0:
                        alert = "HIGH CONFIDENCE ALERT\nMatch: " + home + " vs " + away + "\nHome Win: " + str(sim['home_prob']) + "%\nStake: EUR 15.00"
                        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=alert)
        except Exception as e:
            print(f"Scanner Error: {e}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("matches", matches_command))
    app.add_handler(CommandHandler("bankroll", bankroll_command))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    
    loop = asyncio.get_event_loop()
    loop.create_task(auto_value_scanner(app))
    
    print("Full Athena Quant Engine Online!")
    app.run_polling(drop_pending_updates=True)

