import os
import random
import requests
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ENVIRONMENT & API CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8208471929:AAFFRzvk2QamfEneHG1w4SBoX1kRk4tlf5k")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Sri Lanka Time Zone (UTC +5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Configure Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# --- 1. LIVE FOOTBALL API: FETCH TODAY'S FIXTURES & STATUS ---
def get_today_fixtures():
    fixtures = []
    api_status = "❌ API Disconnected / No Key"
    
    if FOOTBALL_API_KEY:
        try:
            today_date = datetime.now(IST).strftime('%Y-%m-%d')
            url = f"https://v3.football.api-sports.io/fixtures?date={today_date}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            response = requests.get(url, headers=headers, timeout=10)
            print(f"API Response Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json().get("response", [])
                api_status = f"✅ API Connected (Matches Found: {len(data)})"
                print(api_status)
                
                for match in data:
                    utc_time_str = match['fixture']['date']
                    match_utc = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
                    match_ist = match_utc.astimezone(IST)
                    
                    tier = "Mega" if match['league']['name'] in ["Premier League", "La Liga", "UEFA Champions League", "Serie A", "Bundesliga"] else "Domestic"
                    time_formatted = match_ist.strftime('%I:%M %p')
                    
                    fixtures.append({
                        "id": match['fixture']['id'],
                        "home": match['teams']['home']['name'],
                        "away": match['teams']['away']['name'],
                        "home_id": match['teams']['home']['id'],
                        "away_id": match['teams']['away']['id'],
                        "tier": tier,
                        "league": match['league']['name'],
                        "time": time_formatted,
                        "venue": match.get('fixture', {}).get('venue', {}).get('city', 'Stadium')
                    })
            else:
                api_status = f"⚠️ API Error Status: {response.status_code}"
        except Exception as e:
            api_status = f"❌ API Exception: {e}"
            print(api_status)
            
    # API එකෙන් මැච් නැති නම් හෝ දෝෂයක් නම් Fallback ලැයිස්තුව පෙන්වීම
    if not fixtures:
        fixtures = [
            {"id": 33, "home": "Manchester United", "away": "Arsenal", "home_id": 33, "away_id": 42, "tier": "Mega", "league": "Premier League", "time": "Today", "venue": "Manchester"},
            {"id": 34, "home": "Chelsea", "away": "Liverpool", "home_id": 49, "away_id": 40, "tier": "Mega", "league": "Premier League", "time": "Today", "venue": "London"}
        ]
    return fixtures, api_status

# --- SEARCH TEAM DYNAMICALLY FROM API IF NOT IN LIST ---
def search_team_fixture(team_name):
    if FOOTBALL_API_KEY:
        try:
            search_url = f"https://v3.football.api-sports.io/teams?search={team_name}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            res = requests.get(search_url, headers=headers, timeout=5)
            if res.status_code == 200:
                teams_data = res.json().get("response", [])
                if teams_data:
                    team_id = teams_data[0]['team']['id']
                    
                    fix_url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&next=1"
                    fix_res = requests.get(fix_url, headers=headers, timeout=5)
                    if fix_res.status_code == 200:
                        fix_data = fix_res.json().get("response", [])
                        if fix_data:
                            m = fix_data[0]
                            return {
                                "id": m['fixture']['id'],
                                "home": m['teams']['home']['name'],
                                "away": m['teams']['away']['name'],
                                "home_id": m['teams']['home']['id'],
                                "away_id": m['teams']['away']['id'],
                                "tier": "Mega",
                                "league": m['league']['name'],
                                "time": "Upcoming",
                                "venue": m.get('fixture', {}).get('venue', {}).get('city', 'Stadium')
                            }
        except Exception as e:
            print(f"Team Search Error: {e}")
    return None

# --- 2. LIVE WEATHER API ---
def get_live_weather(venue_city):
    if WEATHER_API_KEY and venue_city:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={venue_city}&appid={WEATHER_API_KEY}&units=metric"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                w_data = response.json()
                temp = w_data['main']['temp']
                humidity = w_data['main']['humidity']
                condition = w_data['weather'][0]['main'].lower()
                rain_factor = 0.85 if 'rain' in condition else 1.0
                return {"temp": temp, "humidity": humidity, "rain_factor": rain_factor}
        except Exception as e:
            print(f"Weather API Error: {e}")
    return {"temp": 20.0, "humidity": 50, "rain_factor": 1.0}

# --- 3. INJURIES API ---
def get_team_injuries(fixture_id):
    if FOOTBALL_API_KEY and fixture_id:
        try:
            url = f"https://v3.football.api-sports.io/injuries?fixture={fixture_id}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                return len(response.json().get("response", []))
        except Exception as e:
            print(f"Injuries API Error: {e}")
    return 0

# --- 4. STARTING LINEUPS API ---
def get_match_lineups(fixture_id):
    if FOOTBALL_API_KEY and fixture_id:
        try:
            url = f"https://v3.football.api-sports.io/fixtures/lineups?fixture={fixture_id}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json().get("response", [])
                if data:
                    lineups = {}
                    for team_data in data:
                        team_name = team_data['team']['name']
                        formation = team_data.get('formation', 'N/A')
                        start_xi = [p['player']['name'] for p in team_data['startXI']]
                        substitutes = [p['player']['name'] for p in team_data['substitutes']]
                        lineups[team_name] = {
                            "formation": formation,
                            "start_xi": start_xi,
                            "substitutes": substitutes
                        }
                    return lineups
        except Exception as e:
            print(f"Lineups API Error: {e}")
    return None

# --- 5. LIVE STATS API ---
def get_live_match_stats(fixture_id):
    if FOOTBALL_API_KEY and fixture_id:
        try:
            url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json().get("response", [])
                if data:
                    stats_summary = {}
                    for team_stat in data:
                        t_name = team_stat['team']['name']
                        stats_list = team_stat['statistics']
                        possession = "50%"
                        shots_on_target = 0
                        for s in stats_list:
                            if s['type'] == 'Ball Possession':
                                possession = s['value']
                            elif s['type'] == 'Shots on Goal':
                                shots_on_target = s['value']
                        stats_summary[t_name] = {
                            "possession": possession,
                            "shots_on_target": shots_on_target
                        }
                    return stats_summary
        except Exception as e:
            print(f"Live Stats API Error: {e}")
    return None

# --- 6. ADVANCED H2H & STATS ---
def get_advanced_match_stats(home_id, away_id):
    h2h_goals_avg = 2.5
    fatigue_home = 1.0
    fatigue_away = 1.0
    
    if FOOTBALL_API_KEY and home_id and away_id:
        try:
            h2h_url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}"
            headers = {
                'x-apisports-key': FOOTBALL_API_KEY
            }
            h2h_res = requests.get(h2h_url, headers=headers, timeout=5)
            if h2h_res.status_code == 200:
                h2h_data = h2h_res.json().get("response", [])
                if h2h_data:
                    total_goals = sum([m['goals']['home'] + m['goals']['away'] for m in h2h_data[:5] if m['goals']['home'] is not None])
                    if len(h2h_data[:5]) > 0:
                        h2h_goals_avg = total_goals / len(h2h_data[:5])

            for team_id, is_home in [(home_id, True), (away_id, False)]:
                fix_url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=3"
                fix_res = requests.get(fix_url, headers=headers, timeout=5)
                if fix_res.status_code == 200:
                    matches = fix_res.json().get("response", [])
                    if len(matches) >= 3:
                        if is_home:
                            fatigue_home = 0.90
                        else:
                            fatigue_away = 0.90
        except Exception as e:
            print(f"Stats API Error: {e}")
            
    return {"h2h_avg": h2h_goals_avg, "fatigue_home": fatigue_home, "fatigue_away": fatigue_away}

# --- 7. SIMULATION ENGINE ---
def run_advanced_quant_simulation(match_data, simulations=12000):
    home = match_data.get("home", "Home Team")
    away = match_data.get("away", "Away Team")
    tier = match_data.get("tier", "Mega")
    venue = match_data.get("venue", "Stadium")
    fix_id = match_data.get("id")
    home_id = match_data.get("home_id")
    away_id = match_data.get("away_id")
    
    weather = get_live_weather(venue)
    injuries_count = get_team_injuries(fix_id)
    adv_stats = get_advanced_match_stats(home_id, away_id)
    
    rain_fx = weather["rain_factor"]
    fatigue_h = adv_stats["fatigue_home"]
    fatigue_a = adv_stats["fatigue_away"]
    tier_multiplier = 2.0 if tier == "Mega" else 1.5
    
    home_wins, away_wins, draws, btts_count, over_25_count = 0, 0, 0, 0, 0
    
    for _ in range(simulations):
        form_home = random.uniform(0.95, 1.25) * fatigue_h - (injuries_count * 0.02)
        form_away = random.uniform(0.90, 1.20) * fatigue_a
        
        home_xg = (random.uniform(0.8, 2.5) * form_home * rain_fx) / tier_multiplier
        away_xg = (random.uniform(0.6, 2.2) * form_away * rain_fx) / tier_multiplier
        
        home_goals = int(random.uniform(0, 3) < home_xg)
        away_goals = int(random.uniform(0, 3) < away_xg)
        
        if home_goals > away_goals: home_wins += 1
        elif away_goals > home_goals: away_wins += 1
        else: draws += 1
            
        if home_goals > 0 and away_goals > 0: btts_count += 1
        if (home_goals + away_goals) > 2.5: over_25_count += 1

    return {
        "home": home, "away": away, "weather": weather, "injuries": injuries_count,
        "home_prob": round((home_wins / simulations) * 100, 1),
        "away_prob": round((away_wins / simulations) * 100, 1),
        "draw_prob": round((draws / simulations) * 100, 1),
        "btts_prob": round((btts_count / simulations) * 100, 1),
        "over25_prob": round((over_25_count / simulations) * 100, 1)
    }

# --- GEMINI AI ANALYSIS GENERATOR ---
def generate_gemini_insight(match_name, res, lineups):
    if not gemini_model:
        return "Gemini API key not configured. Standard Quant Report applied."
    
    prompt = f"""
    You are an elite sports betting quant analyst and football expert covering 7 expert lenses (Tactical, Value/Odds, Risk Management, Weather/Physics, Injuries/Squad, Momentum, Bankroll). 
    Analyze this match data for {match_name}:
    - Home Win Prob: {res['home_prob']}%
    - Away Win Prob: {res['away_prob']}%
    - Draw Prob: {res['draw_prob']}%
    - BTTS Prob: {res['btts_prob']}%
    - Over 2.5 Prob: {res['over25_prob']}%
    - Weather Temp: {res['weather']['temp']}C, Rain Factor: {res['weather']['rain_factor']}
    - Injuries Count: {res['injuries']}
    - Lineups: {lineups if lineups else 'Not yet announced'}
    
    Provide a short, punchy, professional betting recommendation (Value Back bet and Exchange Lay bet) based on these quantitative metrics incorporating the 7 expert lenses. Keep it under 150 words.
    """
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Insight generation failed: {e}"

# --- TELEGRAM COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🔥 *Athena Quant Engine: Ultimate Gemini AI Edition* 🔥\n\n"
        "✨ *Connected to Lineups, Live Stats, Weather & Gemini AI (SL Time)*\n\n"
        "📌 *Commands:*\n"
        "• `/matches` - View today's fixtures & API Status\n"
        "• `/analyze_full [Index or Team Name]` - Deep AI Quant Report\n"
        "• `/live_analyze [Index/Name]` - Live In-Play Tactical Scan\n"
        "• `/hedge_calc [Stake] [Original Odds] [Cover Odds]`\n"
        "• `/bankroll`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fixtures, api_status = get_today_fixtures()
    keyboard = [
        [InlineKeyboardButton("🏆 Top Tier Fixtures", callback_data="tier_premier")],
        [InlineKeyboardButton("⚽ Domestic / Other Fixtures", callback_data="tier_domestic")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_msg = f"🔌 *API Status:* {api_status}\n\nකරුණාකර ලීගය තෝරන්න:"
    await update.message.reply_text(status_msg, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    fixtures, api_status = get_today_fixtures()
    selected_tier = "Mega" if "premier" in query.data else "Domestic"
    filtered = [m for m in fixtures if m["tier"] == selected_tier]
    if not filtered: filtered = fixtures
        
    text = f"🇱🇰 *Today's Fixtures ({selected_tier}):*\n🔌 _{api_status}_\n\n"
    for idx, m in enumerate(filtered):
        match_time = m.get('time', 'Today')
        text += f"[{idx}] {m['home']} vs {m['away']}\n    🕒 *Time:* {match_time} | 🏆 _{m.get('league', 'League')}_\n\n"
    text += "👉 Use: `/analyze_full [Index]` or `/analyze_full Real Madrid`"
    await query.edit_message_text(text=text, parse_mode="Markdown")

async def analyze_full_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ මචන් Match Index එකක් හෝ Team Name එකක් දෙන්න!\nඋදා: `/analyze_full 0` හෝ `/analyze_full Arsenal`", parse_mode="Markdown")
        return
    
    query_arg = " ".join(context.args).lower()
    fixtures, api_status = get_today_fixtures()
    matched = None
    
    if query_arg.isdigit():
        idx = int(query_arg)
        if 0 <= idx < len(fixtures): 
            matched = fixtures[idx]
    else:
        for m in fixtures:
            if query_arg in m["home"].lower() or query_arg in m["away"].lower():
                matched = m
                break
        if not matched:
            await update.message.reply_text(f"🔍 '{query_arg}' සඳහා API එකෙන් සෘජුවම මැච් එකක් සොයමින් පවතී...")
            matched = search_team_fixture(" ".join(context.args))
                
    if not matched:
        await update.message.reply_text(f"❌ '{query_arg}' සඳහා ක්‍රියාකාරී මැච් එකක් හමු නොවීය. (API Status: {api_status})")
        return

    res = run_advanced_quant_simulation(matched)
    lineups = get_match_lineups(matched["id"])
    ai_insight = generate_gemini_insight(f"{res['home']} vs {res['away']}", res, lineups)
    
    lineup_text = ""
    if lineups:
        for team, l_data in lineups.items():
            lineup_text += f"• *{team}* ({l_data['formation']}) ✅\n"
    else:
        lineup_text = "Lineups not announced yet.\n"

    report = (
        f"⚡ *ATHENA GEMINI AI QUANT REPORT* ⚡\n\n"
        f"🏟️ **{res['home']} vs {res['away']}**\n"
        f"🌤️ Weather: {res['weather']['temp']}°C | Rain: {res['weather']['rain_factor']}\n"
        f"🏥 Injuries: {res['injuries']} players\n\n"
        f"👕 *Lineups:*\n{lineup_text}\n"
        f"📊 *Probabilities:*\n"
        f"• Home: **{res['home_prob']}%** | Draw: **{res['draw_prob']}%** | Away: **{res['away_prob']}%**\n"
        f"• BTTS: **{res['btts_prob']}%** | Over 2.5: **{res['over25_prob']}%**\n\n"
        f"🤖 *Gemini AI 7-Lens Expert Strategy:*\n{ai_insight}"
    )
    await update.message.reply_text(report, parse_mode="Markdown")

async def live_analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ මැච් එකක් සඳහා Index එකක් හෝ Team Name එකක් දෙන්න!\nඋදා: `/live_analyze 0`", parse_mode="Markdown")
        return
    
    query_arg = " ".join(context.args).lower()
    fixtures, _ = get_today_fixtures()
    matched = None
    
    if query_arg.isdigit() and int(query_arg) < len(fixtures):
        matched = fixtures[int(query_arg)]
    else:
        for m in fixtures:
            if query_arg in m["home"].lower() or query_arg in m["away"].lower():
                matched = m
                break
        if not matched:
            matched = search_team_fixture(" ".join(context.args))

    if not matched:
        await update.message.reply_text("❌ මැච් එක හමු නොවීය.")
        return
    
    res = run_advanced_quant_simulation(matched)
    live_stats = get_live_match_stats(matched["id"])
    
    stats_text = ""
    if live_stats:
        for team, s_data in live_stats.items():
            stats_text += f"• *{team}* -> Poss: {s_data['possession']} | Shots on Target: {s_data['shots_on_target']}\n"
    else:
        stats_text = "Match not live yet or stats syncing...\n"

    live_report = (
        f"🔴 *ATHENA: LIVE IN-PLAY SCAN* 🔴\n\n"
        f"🏟️ **{res['home']} vs {res['away']}**\n"
        f"{stats_text}\n"
        f"⚡ *Live BTTS Probability:* **{res['btts_prob']}%**"
    )
    await update.message.reply_text(live_report, parse_mode="Markdown")

async def hedge_calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("⚠️ විදිහ: `/hedge_calc [Stake] [Orig Odds] [Cover Odds]`", parse_mode="Markdown")
        return
    orig_stake, orig_odds, cover_odds = float(context.args[0]), float(context.args[1]), float(context.args[2])
    orig_payout = orig_stake * orig_odds
    cover_stake = orig_payout / cover_odds
    net_profit = orig_payout - (orig_stake + cover_stake)
    await update.message.reply_text(f"⚖️ *Hedge Cover Stake:* €{round(cover_stake, 2)} | *Net Profit:* €{round(net_profit, 2)}", parse_M="Markdown")

async def bankroll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 *Bankroll:* €100.00 | Protected & Gemini AI Synced.", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("matches", matches_command))
    app.add_handler(CommandHandler("analyze_full", analyze_full_command))
    app.add_handler(CommandHandler("live_analyze", live_analyze_command))
    app.add_handler(CommandHandler("hedge_calc", hedge_calc_command))
    app.add_handler(CommandHandler("bankroll", bankroll_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Athena Gemini AI Quant Master Bot is running with API-Sports Headers & Custom Team Search...")
    app.run_polling()

if __name__ == "__main__":
    main()
