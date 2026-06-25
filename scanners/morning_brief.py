"""
VRAI Trade Buddy — Morning Brief
Runs at 8:30 AM every trading day
Gives complete market overview before open
"""

import requests
from datetime import datetime
from data.market_data import fetcher
from core.brain import brain


def get_global_cues() -> dict:
    """Fetch global market data from free APIs"""
    cues = {}
    try:
        # Using Yahoo Finance API (free, no auth)
        symbols = {
            "S&P 500": "^GSPC",
            "Dow Jones": "^DJI",
            "Nasdaq": "^IXIC",
            "Nikkei": "^N225",
            "Hang Seng": "^HSI",
            "SGX Nifty": "^NSEI"
        }
        for name, symbol in symbols.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                data = r.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
                cues[name] = {
                    "price": price,
                    "prev_close": prev,
                    "change_pct": round((price - prev) / prev * 100, 2) if prev else 0
                }
            except:
                pass
    except Exception as e:
        print(f"[WARN] Global cues fetch failed: {e}")
    return cues


def get_commodity_prices() -> dict:
    """Get Gold, Silver, Crude prices"""
    prices = {}
    try:
        commodities = {
            "Crude Oil (WTI)": "CL=F",
            "Gold": "GC=F",
            "Silver": "SI=F"
        }
        for name, symbol in commodities.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                data = r.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
                prices[name] = {
                    "price": price,
                    "change_pct": round((price - prev) / prev * 100, 2) if prev else 0
                }
            except:
                pass
    except Exception as e:
        print(f"[WARN] Commodity prices failed: {e}")
    return prices


def get_crypto_prices() -> dict:
    """Get BTC and ETH prices (free CoinGecko API)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, timeout=8)
        data = r.json()
        return {
            "Bitcoin": {
                "price": data["bitcoin"]["usd"],
                "change_pct": round(data["bitcoin"].get("usd_24h_change", 0), 2)
            },
            "Ethereum": {
                "price": data["ethereum"]["usd"],
                "change_pct": round(data["ethereum"].get("usd_24h_change", 0), 2)
            }
        }
    except Exception as e:
        print(f"[WARN] Crypto prices failed: {e}")
        return {}


def format_change(pct: float) -> str:
    """Format percentage change with emoji"""
    if pct > 0.5:
        return f"🟢 +{pct:.2f}%"
    elif pct < -0.5:
        return f"🔴 {pct:.2f}%"
    else:
        return f"⚪ {pct:.2f}%"


def generate_morning_brief() -> str:
    """Generate complete morning brief"""
    print(f"[MORNING] Generating brief at {datetime.now().strftime('%H:%M:%S')}")

    # Fetch all data
    global_cues = get_global_cues()
    commodities = get_commodity_prices()
    crypto = get_crypto_prices()
    fii_dii = fetcher.get_fii_dii_data()
    nifty_walls = fetcher.find_oi_walls("NIFTY")
    vix = fetcher.get_vix()

    # Build data package for AI
    market_data = {
        "global": global_cues,
        "commodities": commodities,
        "crypto": crypto,
        "fii_dii": fii_dii,
        "nifty_oi_walls": nifty_walls,
        "india_vix": vix
    }

    # Get AI interpretation
    ai_brief = brain.analyze_market_data(
        market_data,
        "Generate morning market brief for Ashraf. Today's key theme, what to watch, market bias for the day, and any risks. Keep it punchy — like a trading desk morning call. Hinglish mein."
    )

    # Format the message
    global_section = ""
    for name, data in global_cues.items():
        global_section += f"   {name}: {format_change(data.get('change_pct', 0))}\n"

    commodity_section = ""
    for name, data in commodities.items():
        commodity_section += f"   {name}: ${data.get('price', 0):,.2f} {format_change(data.get('change_pct', 0))}\n"

    crypto_section = ""
    for name, data in crypto.items():
        crypto_section += f"   {name}: ${data.get('price', 0):,.0f} {format_change(data.get('change_pct', 0))}\n"

    fii_text = ""
    if fii_dii:
        fii_net = float(fii_dii.get("fii_net", 0))
        dii_net = float(fii_dii.get("dii_net", 0))
        fii_emoji = "🟢" if fii_net > 0 else "🔴"
        dii_emoji = "🟢" if dii_net > 0 else "🔴"
        fii_text = f"""
💰 FII/DII (Previous Day):
   FII: {fii_emoji} ₹{fii_net:,.0f} Cr
   DII: {dii_emoji} ₹{dii_net:,.0f} Cr"""

    oi_text = ""
    if nifty_walls:
        spot = nifty_walls.get("spot", 0)
        ce_walls = nifty_walls.get("ce_walls", [])
        pe_walls = nifty_walls.get("pe_walls", [])
        pcr = nifty_walls.get("pcr", 0)
        ce_wall_str = f"{ce_walls[0]['strike']}" if ce_walls else "N/A"
        pe_wall_str = f"{pe_walls[0]['strike']}" if pe_walls else "N/A"
        oi_text = f"""
📊 Nifty OI Walls:
   Spot: {spot:,.2f}
   CE Wall (Resistance): {ce_wall_str}
   PE Wall (Support): {pe_wall_str}
   PCR: {pcr:.2f} | VIX: {vix}"""

    message = f"""
🌅 GOOD MORNING, ASHRAF! 
📅 {datetime.now().strftime('%A, %d %b %Y')} | 8:30 AM

🌍 GLOBAL CUES:
{global_section}
🛢️ COMMODITIES:
{commodity_section}
🪙 CRYPTO:
{crypto_section}{fii_text}{oi_text}

🤖 BUDDY'S MORNING CALL:
{ai_brief}

━━━━━━━━━━━━━━━━━━━━
⏰ BTST SCAN: 2:00 PM
⚡ GAMMA WATCH: All day
━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()
