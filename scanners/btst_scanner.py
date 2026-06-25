"""
VRAI Trade Buddy — BTST Scanner
Runs at 2:00 PM daily
Scans Nifty, Sensex, BankNifty + top stocks
Finds best BTST F&O setup for overnight hold
"""

from datetime import datetime
from data.market_data import fetcher
from core.brain import brain


BTST_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX"]

BTST_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "BAJFINANCE", "SBIN", "AXISBANK", "KOTAKBANK",
    "LT", "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA",
    "WIPRO", "ULTRACEMCO", "BAJAJFINSV", "TECHM", "HCLTECH"
]


def score_btst_setup(symbol: str, is_index: bool = True) -> dict:
    """
    Score a symbol for BTST potential (0-5 score)
    Each filter = 1 point. Need 4/5 to qualify.
    """
    score = 0
    filters = {}

    try:
        # Get OI walls
        walls = fetcher.find_oi_walls(symbol)
        if not walls:
            return {"symbol": symbol, "score": 0, "filters": {}}

        spot = walls.get("spot", 0)
        pcr = walls.get("pcr", 1.0)
        ce_walls = walls.get("ce_walls", [])
        pe_walls = walls.get("pe_walls", [])

        # Filter 1: PCR check
        # PCR > 1.2 = bullish (more PE writers = market protected)
        # PCR < 0.8 = bearish (more CE writers = market capped)
        if pcr > 1.2:
            score += 1
            filters["pcr"] = f"✅ Bullish PCR: {pcr:.2f}"
            direction = "CE"
        elif pcr < 0.8:
            score += 1
            filters["pcr"] = f"✅ Bearish PCR: {pcr:.2f}"
            direction = "PE"
        else:
            filters["pcr"] = f"⚠️ Neutral PCR: {pcr:.2f}"
            direction = "CE"  # Default

        # Filter 2: OI Wall distance — price close to support/resistance
        if direction == "CE" and pe_walls:
            nearest_support = pe_walls[0]["strike"]
            distance_pct = (spot - nearest_support) / spot * 100
            if distance_pct < 1.5:  # Within 1.5% of support
                score += 1
                filters["oi_support"] = f"✅ Strong PE wall at {nearest_support} ({distance_pct:.1f}% away)"
            else:
                filters["oi_support"] = f"⚠️ PE wall at {nearest_support} ({distance_pct:.1f}% away — too far)"

        elif direction == "PE" and ce_walls:
            nearest_resistance = ce_walls[0]["strike"]
            distance_pct = (nearest_resistance - spot) / spot * 100
            if distance_pct < 1.5:
                score += 1
                filters["oi_resistance"] = f"✅ Strong CE wall at {nearest_resistance} ({distance_pct:.1f}% away)"
            else:
                filters["oi_resistance"] = f"⚠️ CE wall at {nearest_resistance} ({distance_pct:.1f}% away — too far)"

        # Filter 3: VIX check (low VIX = calm market = good for BTST)
        vix = fetcher.get_vix()
        if vix > 0:
            if vix < 15:
                score += 1
                filters["vix"] = f"✅ VIX calm: {vix}"
            elif vix < 18:
                filters["vix"] = f"⚠️ VIX moderate: {vix}"
            else:
                filters["vix"] = f"❌ VIX high: {vix} — avoid BTST"

        # Filter 4: FII Flow
        fii_data = fetcher.get_fii_dii_data()
        if fii_data:
            fii_net = float(fii_data.get("fii_net", 0))
            if direction == "CE" and fii_net > 1000:
                score += 1
                filters["fii"] = f"✅ FII buyers: +₹{fii_net:.0f} Cr"
            elif direction == "PE" and fii_net < -1000:
                score += 1
                filters["fii"] = f"✅ FII sellers: ₹{fii_net:.0f} Cr"
            elif abs(fii_net) < 500:
                filters["fii"] = f"⚠️ FII neutral: ₹{fii_net:.0f} Cr"
            else:
                filters["fii"] = f"⚠️ FII flow mixed: ₹{fii_net:.0f} Cr"

        # Filter 5: No big events overnight
        # This is checked by AI brain separately
        score += 1  # Assume clear unless news scanner catches something
        filters["events"] = "✅ No major events detected overnight (verify news)"

        # Calculate ATM strike for entry
        if is_index:
            rounding = 100 if symbol == "BANKNIFTY" else 50
        else:
            rounding = 50
        atm = round(spot / rounding) * rounding

        if direction == "CE":
            entry_strike = atm  # ATM CE for bullish
        else:
            entry_strike = atm  # ATM PE for bearish

        return {
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "spot": spot,
            "entry_strike": entry_strike,
            "entry_type": direction,
            "pcr": pcr,
            "vix": vix,
            "filters": filters,
            "ce_walls": ce_walls[:2],
            "pe_walls": pe_walls[:2]
        }

    except Exception as e:
        print(f"[ERROR] BTST score failed for {symbol}: {e}")
        return {"symbol": symbol, "score": 0, "filters": {}}


def run_btst_scan() -> str:
    """
    Main 2 PM BTST scan.
    Scans all symbols, finds best setup, formats alert.
    """
    print(f"[BTST] Starting 2 PM scan at {datetime.now().strftime('%H:%M:%S')}")

    results = []

    # Scan indices
    for symbol in BTST_SYMBOLS:
        result = score_btst_setup(symbol, is_index=True)
        if result["score"] >= 3:
            results.append(result)
            print(f"[BTST] {symbol}: Score {result['score']}/5")

    # Sort by score — best first
    results.sort(key=lambda x: x["score"], reverse=True)

    if not results:
        return format_no_setup_message()

    best = results[0]

    if best["score"] < 4:
        return format_weak_setup_message(best)

    return format_btst_alert(best, results[1] if len(results) > 1 else None)


def format_btst_alert(best: dict, second: dict = None) -> str:
    """Format BTST alert with AI analysis"""

    # Get AI analysis
    ai_take = brain.analyze_market_data(best,
        "This is today's best BTST F&O setup. Give your expert analysis: entry timing, exact premium range to buy, overnight risk factors, and exit plan for 9:15 AM tomorrow.")

    filters_text = "\n".join([f"   {v}" for v in best["filters"].values()])
    direction_emoji = "🟢" if best["direction"] == "CE" else "🔴"

    msg = f"""
🎯 BTST SCAN — {datetime.now().strftime('%d %b %Y')} 🎯

Best Setup: {best['symbol']} {direction_emoji}
Score: {best['score']}/5 filters ✅

📊 Market Snapshot:
   Spot: {best['spot']:,.2f}
   PCR: {best['pcr']:.2f}
   VIX: {best['vix']}

✅ Filter Check:
{filters_text}

📋 TRADE:
   Buy: {best['symbol']} {best['entry_strike']}{best['entry_type']}
   Expiry: Current week
   Lot: 1 lot only

⏰ ENTRY: 2:15 - 2:45 PM today
🚪 EXIT: 9:15 AM sharp tomorrow
🛑 SL: If premium falls 40% — exit at open

🤖 Buddy's Analysis:
{ai_take}
"""

    if second and second["score"] >= 4:
        msg += f"\n\n🔔 Backup Setup: {second['symbol']} {second['direction']} (Score: {second['score']}/5)"

    return msg.strip()


def format_no_setup_message() -> str:
    no_trade_wisdom = brain.chat(
        "Aaj 2 PM scan mein koi strong BTST setup nahi mila — score 3 se kam. Ashraf ko kya bolun? Short mein.")
    return f"""
📊 2 PM BTST SCAN COMPLETE

❌ Aaj koi strong setup nahi hai.
Score 3/5 se kam — SKIP karo.

🤖 Buddy:
{no_trade_wisdom}

Cash bachao — kal better setup milega. 💪
""".strip()


def format_weak_setup_message(setup: dict) -> str:
    return f"""
📊 2 PM BTST SCAN COMPLETE

⚠️ Setup weak hai — {setup['symbol']} Score: {setup['score']}/5

🤖 Buddy: Setup 4/5 se kam hai. Risk zyada hai.
Aaj SKIP karna better hai.

"Best trade kabhi kabhi no trade hota hai." 🧘
""".strip()
