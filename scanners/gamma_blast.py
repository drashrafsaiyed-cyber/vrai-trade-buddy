"""
VRAI Trade Buddy — Gamma Blast Scanner
Detects when OI walls break and premium is about to explode
Runs continuously during market hours
"""

import time
from datetime import datetime
from typing import Optional
from data.market_data import fetcher
from core.brain import brain

# Symbols to watch for Gamma Blast
WATCH_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY"]

# State tracking — remember previous OI walls
previous_walls = {}
blast_alerts_sent = set()  # Avoid duplicate alerts


def check_gamma_blast(symbol: str) -> Optional[dict]:
    """
    Check if a Gamma Blast is happening for a symbol.
    
    Gamma Blast = OI wall breaks + price sustains above/below wall
    
    Returns alert dict if blast detected, None otherwise
    """
    try:
        walls = fetcher.find_oi_walls(symbol)
        if not walls:
            return None

        spot = walls.get("spot", 0)
        ce_walls = walls.get("ce_walls", [])
        pe_walls = walls.get("pe_walls", [])
        vix = fetcher.get_vix()

        # Safety check — don't alert in last 30 min (2:30-3:00 PM trap)
        now = datetime.now()
        if now.hour == 14 and now.minute >= 30:
            return None
        if now.hour >= 15:
            return None

        # ---- CE WALL BREAK CHECK ----
        if ce_walls:
            strongest_ce_wall = ce_walls[0]
            ce_strike = strongest_ce_wall["strike"]
            ce_oi = strongest_ce_wall["oi"]

            # Check if price has broken above CE wall
            if spot > ce_strike:
                alert_key = f"{symbol}_CE_{ce_strike}_{now.strftime('%Y%m%d')}"

                if alert_key not in blast_alerts_sent:
                    # Check next CE wall for target
                    next_ce_target = ce_walls[1]["strike"] if len(ce_walls) > 1 else ce_strike + 200

                    # Verify: wall OI should be significant (> 10 lakh contracts)
                    if ce_oi > 1000000:
                        blast_alerts_sent.add(alert_key)
                        return {
                            "type": "GAMMA_BLAST",
                            "direction": "BULLISH",
                            "symbol": symbol,
                            "wall_broken": ce_strike,
                            "wall_oi": ce_oi,
                            "spot": spot,
                            "entry_type": "CE",
                            "entry_strike": ce_strike,
                            "target_strike": next_ce_target,
                            "vix": vix,
                            "time": now.strftime("%H:%M"),
                            "ce_ltp": strongest_ce_wall.get("ltp", 0)
                        }

        # ---- PE WALL BREAK CHECK ----
        if pe_walls:
            strongest_pe_wall = pe_walls[0]
            pe_strike = strongest_pe_wall["strike"]
            pe_oi = strongest_pe_wall["oi"]

            # Check if price has broken below PE wall
            if spot < pe_strike:
                alert_key = f"{symbol}_PE_{pe_strike}_{now.strftime('%Y%m%d')}"

                if alert_key not in blast_alerts_sent:
                    next_pe_target = pe_walls[1]["strike"] if len(pe_walls) > 1 else pe_strike - 200

                    if pe_oi > 1000000:
                        blast_alerts_sent.add(alert_key)
                        return {
                            "type": "GAMMA_BLAST",
                            "direction": "BEARISH",
                            "symbol": symbol,
                            "wall_broken": pe_strike,
                            "wall_oi": pe_oi,
                            "spot": spot,
                            "entry_type": "PE",
                            "entry_strike": pe_strike,
                            "target_strike": next_pe_target,
                            "vix": vix,
                            "time": now.strftime("%H:%M"),
                            "pe_ltp": strongest_pe_wall.get("ltp", 0)
                        }

        return None

    except Exception as e:
        print(f"[ERROR] Gamma blast check failed for {symbol}: {e}")
        return None


def format_gamma_blast_alert(blast: dict) -> str:
    """Format Gamma Blast alert for Telegram/notification"""
    direction_emoji = "🚀" if blast["direction"] == "BULLISH" else "🔻"
    entry_type = blast["entry_type"]
    ltp_key = "ce_ltp" if entry_type == "CE" else "pe_ltp"
    ltp = blast.get(ltp_key, 0)

    # Get AI analysis
    ai_analysis = brain.analyze_market_data(blast, 
        f"Gamma Blast detected on {blast['symbol']}. Give entry advice, risk warning, and target confirmation based on OI data.")

    message = f"""
⚡ GAMMA BLAST DETECTED ⚡ {direction_emoji}

📊 Index: {blast['symbol']}
💥 Wall Broken: {blast['wall_broken']} {entry_type} 
   (OI: {blast['wall_oi']:,} contracts)
⏰ Break Time: {blast['time']}
📍 Spot Now: {blast['spot']:,.2f}

✅ ENTRY SIGNAL:
   Option: {blast['symbol']} {blast['entry_strike']}{entry_type}
   Current Premium: ₹{ltp}
   
🎯 TARGET: {blast['target_strike']} (next OI wall)
📊 VIX: {blast['vix']}

🤖 Buddy's Take:
{ai_analysis}

⚠️ Exit: When price hits {blast['target_strike']} OR 2:30 PM
❌ Don't hold overnight — this is intraday Gamma play
"""
    return message.strip()


def run_gamma_blast_scan(notify_callback=None):
    """
    Run one scan cycle for all symbols.
    Call this every 5 minutes during market hours.
    """
    print(f"[SCAN] Gamma Blast scan started at {datetime.now().strftime('%H:%M:%S')}")
    alerts = []

    for symbol in WATCH_SYMBOLS:
        blast = check_gamma_blast(symbol)
        if blast:
            alert_message = format_gamma_blast_alert(blast)
            alerts.append(alert_message)
            print(f"[ALERT] Gamma Blast detected: {symbol} {blast['direction']}")

            # Send notification if callback provided
            if notify_callback:
                notify_callback(alert_message)

    if not alerts:
        print(f"[SCAN] No Gamma Blast detected. All clear.")

    return alerts
