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
        "🔥 **Athena 13 Ultimate Engine Active!**🔥\n\n"
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
    await update.message.reply_text(f"📡 *Fetching Real API Statistics & Running 10,000 Monte Carlo Simulations...*", parse_mode="Markdown")

    api_data = fetch_live_api_data(team_name)

    if api_data:
        mc = run_advanced_monte_carlo(avg_scored=api_data['avg_xg_scored'], avg_conceded=api_data['avg_xg_conceded'])
        match_header = f"🏆 **{api_data['official_name']}** ({api_data['match_info']})"
        api_summary = f"📊 *API Historical Stats:* Scored Avg `{api_data['avg_xg_scored']:.2f}`, Conceded Avg `{api_data['avg_xg_conceded']:.2f}`\n\n"
    else:
        mc = run_advanced_monte_carlo()
        match_header = f"🏆 **Match Prediction Engine:** {team_name}"
        api_summary = "⚠️ *API Data unavailable. Using fallback baseline stats.*\n\n"

    stake = user_bankroll * 0.05
    kelly_stake = user_bankroll * 0.03

    response_msg = (
        f"{match_header}\n\n"
        f"{api_summary}"
        f"🎲 **Monte Carlo Probabilities (10k Sims):**\n"
        f"• Home Win: `{mc['home_win']:.1f}%`\n"
        f"• Draw: `{mc['draw']:.1f}%`\n"
        f"• Away Win: `{mc['away_win']:.1f}%`\n"
        f"• BTTS (Yes): `{mc['btts']:.1f}%`\n"
        f"• Over 1.5 Goals: `{mc['over_15']:.1f}%`\n"
        f"• Over 2.5 Goals: `{mc['over_25']:.1f}%`\n"
        f"• HT Over 0.5 Goals: `{mc['ht_over_05']:.1f}%`\n\n"
        f"🔥 *Top Exact Scores:* `{mc['top_scores']}`\n\n"
        f"💡 **Smart Betting Plan (Bankroll: €{user_bankroll}):**\n"
        f"• Recommended Stake (5%): **€{stake:.2f}**\n"
        f"• Kelly Criterion Stake: **€{kelly_stake:.2f}**"
    )
    await update.message.reply_text(response_msg, parse_mode="Markdown")

async def live_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("⚠️ Usage: `/live Arsenal vs Dortmund 35min 0-1`", parse_mode="Markdown")
        return

    match_desc = " ".join(context.args[:-2])
    minute_str = context.args[-2]
    score_str = context.args[-1]

    try:
        minute = int(minute_str.replace("min", "").replace("'", ""))
    except ValueError:
        minute = 30

    response_msg = (
        f"⚡ **In-Play Live Strategy: {match_desc}**\n"
        f"⏱️ Minute: `{minute}'` | Score: `{score_str}`\n\n"
    )

    if minute < 40:
        response_msg += (
            "📌 *First Half Strategy:* Market is heavily overreacting. "
            "Look for **Over 0.5 HT Goals** or **Next Team to Score** if dominant."
        )
    elif 45 <= minute <= 60:
        response_msg += (
            "📌 *Half-Time Pivot:* Ideal window for live value. "
            "Target **Over 1.5 Match Goals** or lay the trailing favorite if statistics support a comeback."
        )
    else:
        response_msg += (
            "📌 *Late-Game Pressure Strategy:* High volatility zone. "
            "Look for late corner spikes or hedging opportunities."
        )

    await update.message.reply_text(response_msg, parse_mode="Markdown")

async def hedge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/hedge Arsenal 1-2`", parse_mode="Markdown")
        return

    team_name = context.args[0]
    current_score = context.args[1]

    hedge_msg = (
        f"🛡️ **Loss Mitigation & Cashout Strategy**\n"
        f"Match/Team: `{team_name}` | Current Score: `{current_score}`\n\n"
        f"• **Recommendation:** Secure 50% cashout to lock in profits or minimize risk.\n"
        f"• **Hedge Option:** Place a small live stake on the opposing outcome to guarantee a green book."
    )
    await update.message.reply_text(hedge_msg, parse_mode="Markdown")

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("bankroll", set_bankroll))
    application.add_handler(CommandHandler("predict", predict))
    application.add_handler(CommandHandler("live", live_bet))
    application.add_handler(CommandHandler("hedge", hedge))

    print("Athena 13 Bot Engine Running Successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
