import os
import requests
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai

# Load Environment Variables from Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini AI Engine
genai.configure(api_key=GEMINI_API_KEY)

# Default Global Bankroll
user_bankroll = 100.0

# API Football Request Headers
HEADERS = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': API_FOOTBALL_KEY
}

def fetch_live_api_data(team_name):
    """Fetch Historical Form, Goals Scored/Conceded and Match Context via API-Football"""
    try:
        url = f"https://v3.football.api-sports.io/teams?search={team_name}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()                                                                         
        if not res.get('response'):
            return None
        team_id = res['response'][0]['team']['id']
        team_official_name = res['response'][0]['team']['name']
        
        # Get Next Match Details
        next_match_url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&next=1"
        match_res = requests.get(next_match_url, headers=HEADERS, timeout=10).json()
        
        match_info = "Next match info ready"
        if match_res.get('response'):
            fixture = match_res['response'][0]
            home_team = fixture['teams']['home']['name']
            away_team = fixture['teams']['away']['name']
            match_info = f"Upcoming Match: {home_team} vs {away_team}"

        # Fetch Last 5 Historical Matches for Goal Baseline & xG Averages
        stats_url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=5"
        stats_res = requests.get(stats_url, headers=HEADERS, timeout=10).json()
        
        goals_scored = []
        goals_conceded = []
        if stats_res.get('response'):
            for match in stats_res['response']:
                is_home = match['teams']['home']['id'] == team_id
                scored = match['goals']['home'] if is_home else match['goals']['away']
                conceded = match['goals']['away'] if is_home else match['goals']['home']
                if scored is not None:
                    goals_scored.append(scored)
                if conceded is not None:
                    goals_conceded.append(conceded)
                
        avg_xg_scored = float(np.mean(goals_scored)) if goals_scored else 1.65
        avg_xg_conceded = float(np.mean(goals_conceded)) if goals_conceded else 1.10

        return {
            "official_name": team_official_name,
            "match_info": match_info,
            "avg_xg_scored": avg_xg_scored,
            "avg_xg_conceded": avg_xg_conceded,
            "recent_goals_scored": goals_scored,
            "recent_goals_conceded": goals_conceded
        }
    except Exception as e:
        print(f"API Fetch Error: {e}")
        return None

def run_advanced_monte_carlo(avg_scored=1.75, avg_conceded=1.15, simulations=10000):
    """Mathematical Monte Carlo Engine using Poisson Goal Distributions"""
    home_goals = np.random.poisson(avg_scored, simulations)
    away_goals = np.random.poisson(avg_conceded, simulations)
    
    home_wins = np.sum(home_goals > away_goals)
    draws = np.sum(home_goals == away_goals)
    away_wins = np.sum(home_goals < away_goals)
    
    # Calculate Exact Score Frequencies
    scores, counts = np.unique(list(zip(home_goals, away_goals)), axis=0, return_counts=True)
    top_scores = sorted(zip(scores, counts), key=lambda x: x[1], reverse=True)[:3]
    top_score_str = ", ".join([f"{s[0]}-{s[1]} ({(c/simulations)*100:.1f}%)" for s, c in top_scores])

    return {
        "home_win": (home_wins / simulations) * 100,
        "draw": (draws / simulations) * 100,
        "away_win": (away_wins / simulations) * 100,
        "btts": (np.sum((home_goals > 0) & (away_goals > 0)) / simulations) * 100,
        "over_15": (np.sum((home_goals + away_goals) > 1.5) / simulations) * 100,
        "over_25": (np.sum((home_goals + away_goals) > 2.5) / simulations) * 100,
        "ht_over_05": (np.sum((home_goals + away_goals) > 0.8) / simulations) * 100,
        "top_scores": top_score_str
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🔥 **Athena 13 Ultimate Engine Active!**\n\n"
        "Commands:\n"
        "👉 `/bankroll [amount]` - Set your bankroll (e.g. `/bankroll 120`)\n"
        "👉 `/predict [Team]` - Complete Match Predictions & Value Bets\n"
        "👉 `/live [Match] [Minute] [Score]` - In-Play Minute Strategy (e.g. `/live Arsenal vs Dortmund 35min 0-1`)\n"
        "👉 `/hedge [Team] [Score]` - Loss Mitigation & Cashout Strategy"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def set_bankroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_bankroll
    try:
        amount = float(context.args[0])
        user_bankroll = amount
        await update.message.reply_text(f"✅ Bankroll updated to: **€{user_bankroll}**", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: `/bankroll 120`", parse_mode="Markdown")

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/predict Arsenal`", parse_mode="Markdown")
        return

    team_name = " ".join(context.args)
    await update.message.reply_text(f"📡 *Fetching Real API Statistics & Running 10,000 Monte Carlo Simulations for **{team_name}**...*", parse_mode="Markdown")

    api_data = fetch_live_api_data(team_name)

    if api_data:
        mc = run_advanced_monte_carlo(avg_scored=api_data['avg_xg_scored'], avg_conceded=api_data['avg_xg_conceded'])
        match_header = f"{api_data['official_name']} ({api_data['match_info']})"
        api_summary = f"API Historical Stats: Scored Avg {api_data['avg_xg_scored']:.2f}, Conceded Avg {api_data['avg_xg_conceded']:.2f} in last 5 matches."
    else:
        mc = run_advanced_monte_carlo()
        match_header = team_name
        api_summary = "Using default historical baseline statistics."

    prompt = f"""
    You are Athena 13, a top-tier mathematical sports betting algorithm powered by real API data and Monte Carlo simulations.
    Analyze the upcoming match for: {match_header}.
    
    Data Input Summary: {api_summary}
    Monte Carlo Simulation Results (10,000 iterations):
    - Win Probabilities: Win {mc['home_win']:.1f}% | Draw {mc['draw']:.1f}% | Loss {mc['away_win']:.1f}%
    - Goal Probabilities: Over 1.5 ({mc['over_15']:.1f}%) | Over 2.5 ({mc['over_25']:.1f}%) | BTTS ({mc['btts']:.1f}%)
    - Halftime Projection: HT Over 0.5 Goals ({mc['ht_over_05']:.1f}%)
    - Top Simulated Scores: {mc['top_scores']}
    - User Bankroll: €{user_bankroll}

    Generate a complete, highly structured prediction report in clean Telegram Markdown format:
    📌 **MATCH OVERVIEW & REAL-TIME METRICS**
    📊 **MONTE CARLO PROBABILITIES (XG DRIVEN)**
    🎯 **BEST VALUE BETS** (Provide Winner, Asian Handicap, Over/Under with EV context)
    🔢 **MOST LIKELY EXACT SCORES**
    💰 **STAKE ALLOCATION** (Calculated safely using Kelly Criterion for €{user_bankroll})
    ⚠️ **RISK ASSESSMENT & FINAL VERDICT**
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error generating prediction: {str(e)}")

async def live_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4:
        await update.message.reply_text("⚠️ Usage: `/live Arsenal vs Dortmund 35min 0-1`", parse_mode="Markdown")
        return

    match_name = f"{context.args[0]} {context.args[1]} {context.args[2]}"
    minute = context.args[3]
    score = context.args[4] if len(context.args) > 4 else "0-0"

    await update.message.reply_text(f"⏱️ *Athena 13 Live Engine Analyzing...*\nMatch: **{match_name}** | Minute: **{minute}** | Score: **{score}**", parse_mode="Markdown")

    prompt = f"""
    You are Athena 13 Live In-Play Betting Engine.
    Analyze this exact minute-by-minute live game situation:
    Match: {match_name}
    Current Minute: {minute}
    Current Score: {score}
    User Bankroll: €{user_bankroll}

    Generate an urgent, time-sensitive In-Play Strategy in Telegram Markdown:
    ⚡ **IN-PLAY ACTION (AT MINUTE {minute})**
    🎯 **RECOMMENDED LIVE BET** (e.g. Next Goal, Over 1.5 Goals, Live Asian Handicap)
    💰 **EXACT LIVE STAKE (€)** (Safely scaled for €{user_bankroll})
    ⏱️ **VALIDITY WINDOW** (Time window to execute this bet)
    📊 **RISK & LIVE PROBABILITY ASSESSMENT**
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Live Engine Error: {str(e)}")

async def hedge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/hedge Arsenal 0-1`", parse_mode="Markdown")
        return

    team_name = context.args[0]
    score = context.args[1]

    await update.message.reply_text(f"🛡️ *Athena 13 Loss Mitigation System Active...*\nAnalyzing Hedging options for **{team_name}** at **{score}**...", parse_mode="Markdown")

    prompt = f"""
    You are Athena 13 Loss Mitigation & Risk Recovery Engine.
    Team Bet On: {team_name}
    Current Score: {score} (User facing active loss/risk)
    Bankroll: €{user_bankroll}

    Generate an actionable In-Play Loss Mitigation Report in Telegram Markdown:
    🛡️ **LIVE LOSS MINIMIZATION STRATEGY**
    1. **Cashout Recommendation** (Cashout, Partial Cashout, or Hold)
    2. **Counter-Bet / Hedging Selection** (Exact live bet to cover losses)
    3. **Recommended Hedge Stake (€)**
    4. **Risk Comparison** (Hedging Profit/Loss vs Holding Risk)
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hedging Error: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bankroll", set_bankroll))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("live", live_bet))
    app.add_handler(CommandHandler("hedge", hedge))
    
    print("Athena 13 Ultimate Engine Running...")
    app.run_polling()

if __name__ == "__main__":
    main()

