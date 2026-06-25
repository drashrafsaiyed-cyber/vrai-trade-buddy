"""
VRAI Trade Buddy — Main App
FastAPI backend with:
- Web chat interface
- Scheduler (morning brief, BTST scan, gamma blast)
- REST API endpoints
Deploy on Render.com
"""

import os
import sys
import asyncio
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from core.brain import brain
from scanners.morning_brief import generate_morning_brief
from scanners.btst_scanner import run_btst_scan
from scanners.gamma_blast import run_gamma_blast_scan
from notifications.notifier import (
    send_morning_brief, send_btst_alert,
    send_gamma_blast, send_exit_reminder,
    get_notification_log
)

# ============================================
# SCHEDULER SETUP
# ============================================
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def is_trading_day() -> bool:
    """Check if today is a weekday (Mon-Fri)"""
    return datetime.now().weekday() < 5  # 0=Mon, 4=Fri


def is_market_hours() -> bool:
    """Check if market is open"""
    now = datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0)
    market_close = now.replace(hour=15, minute=30, second=0)
    return market_open <= now <= market_close


async def job_morning_brief():
    """8:30 AM — Send morning brief"""
    if not is_trading_day():
        return
    print("[SCHEDULER] Running morning brief...")
    try:
        brief = generate_morning_brief()
        send_morning_brief(brief)
    except Exception as e:
        print(f"[ERROR] Morning brief failed: {e}")


async def job_btst_scan():
    """2:00 PM — Run BTST scan"""
    if not is_trading_day():
        return
    print("[SCHEDULER] Running BTST scan...")
    try:
        result = run_btst_scan()
        send_btst_alert(result)
    except Exception as e:
        print(f"[ERROR] BTST scan failed: {e}")


async def job_gamma_blast():
    """Every 5 minutes during market hours — Gamma blast scan"""
    if not is_trading_day() or not is_market_hours():
        return
    try:
        run_gamma_blast_scan(notify_callback=send_gamma_blast)
    except Exception as e:
        print(f"[ERROR] Gamma blast scan failed: {e}")


async def job_exit_reminder():
    """9:15 AM — Exit reminder for BTST positions"""
    if not is_trading_day():
        return
    print("[SCHEDULER] Sending exit reminder...")
    send_exit_reminder()


# ============================================
# APP LIFECYCLE
# ============================================
_tg_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tg_app
    print("VRAI Trade Buddy starting up...")

    # Schedule jobs
    scheduler.add_job(job_morning_brief, "cron", hour=8, minute=30)
    scheduler.add_job(job_exit_reminder, "cron", hour=9, minute=15)
    scheduler.add_job(job_gamma_blast, "interval", minutes=5)
    scheduler.add_job(job_btst_scan, "cron", hour=14, minute=0)
    scheduler.start()
    print("Scheduler started (8:30 brief / 9:15 exit / 2:00 BTST / 5min gamma)")

    # Start two-way Telegram bot
    try:
        from notifications.telegram_bot import build_application
        _tg_app = build_application()
        await _tg_app.initialize()
        await _tg_app.start()
        await _tg_app.updater.start_polling(drop_pending_updates=True)
        print("Telegram bot polling started — two-way chat active")
    except Exception as e:
        print(f"Telegram bot start failed: {e}")

    yield

    # Shutdown
    if _tg_app:
        try:
            await _tg_app.updater.stop()
            await _tg_app.stop()
            await _tg_app.shutdown()
        except Exception:
            pass
    scheduler.shutdown()
    print("Trade Buddy shutting down...")


# ============================================
# FASTAPI APP
# ============================================
app = FastAPI(
    title="VRAI Trade Buddy",
    description="AI-powered F&O trading companion",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# REQUEST MODELS
# ============================================
class ChatMessage(BaseModel):
    message: str


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve chat UI"""
    with open("static/index.html", "r") as f:
        return f.read()


def _extract_stock_mentions(text: str) -> list:
    """Extract NSE stock symbols mentioned in user message for live price lookup."""
    import re
    # Common NSE large-cap symbols
    known = {
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK",
        "KOTAKBANK", "HINDUNILVR", "ITC", "BHARTIARTL", "WIPRO", "HCLTECH",
        "ASIANPAINT", "MARUTI", "BAJFINANCE", "BAJAJFINSV", "TITAN", "NESTLEIND",
        "ULTRACEMCO", "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP",
        "TATAMOTORS", "TATASTEEL", "HINDALCO", "JSWSTEEL", "COALINDIA",
        "ONGC", "NTPC", "POWERGRID", "ADANIPORTS", "ADANIENT", "TECHM",
        "LTIM", "LT", "M&M", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO",
        "INDUSINDBK", "GRASIM", "BPCL", "IOC", "PIDILITIND", "DABUR",
        "BRITANNIA", "TATACONSUM", "HDFCLIFE", "SBILIFE", "ICICIPRULI",
    }
    words = set(re.findall(r'\b[A-Z][A-Z0-9&\-]{2,14}\b', text.upper()))
    return list(words & known)


@app.post("/chat")
async def chat(msg: ChatMessage):
    """2-way chat — injects full market context (all indices + relevant stocks)."""
    try:
        from data.market_data import fetcher

        # Detect any stock names mentioned
        stocks = _extract_stock_mentions(msg.message)

        # Build rich live context
        context = fetcher.build_market_context(extra_stocks=stocks)
        enriched = context + "\n\nUser: " + msg.message

        response = brain.chat(enriched)
        return {"response": response, "time": datetime.now(_IST).strftime("%H:%M:%S")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/morning")
async def trigger_morning_brief():
    """Manually trigger morning brief"""
    try:
        brief = generate_morning_brief()
        send_morning_brief(brief)
        return {"status": "sent", "preview": brief[:500]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/btst")
async def trigger_btst_scan():
    """Manually trigger BTST scan"""
    try:
        result = run_btst_scan()
        send_btst_alert(result)
        return {"status": "sent", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/gamma")
async def trigger_gamma_scan():
    """Manually trigger Gamma Blast scan"""
    try:
        alerts = run_gamma_blast_scan(notify_callback=send_gamma_blast)
        return {"status": "done", "alerts_found": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notifications")
async def get_notifications():
    """Get all notifications log"""
    return {"notifications": get_notification_log()}


@app.get("/health")
async def health():
    """Health check for Render"""
    return {
        "status": "alive",
        "time": datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "scheduler": scheduler.running
    }


@app.get("/my-ip")
async def my_ip():
    """Returns this server's outbound IP — needed for Angel One SmartAPI whitelist"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.ipify.org?format=json", timeout=5)
            return r.json()
    except Exception:
        return {"ip": "unavailable"}


@app.get("/market/walls")
async def get_oi_walls(symbol: str = "NIFTY"):
    """Get current OI walls for a symbol"""
    from data.market_data import fetcher
    walls = fetcher.find_oi_walls(symbol)
    return walls


@app.get("/market/oi-chat-context")
async def get_oi_chat_context(symbol: str = "NIFTY"):
    """
    Returns OI wall data formatted as a chat-ready string.
    If OI data unavailable, returns honest message so AI doesn't hallucinate.
    """
    from data.market_data import fetcher
    walls = fetcher.find_oi_walls(symbol)
    nifty = fetcher.get_index_quote("NIFTY 50")

    spot = nifty.get("last", 0) if nifty else 0

    if walls and walls.get("spot") and walls.get("ce_walls"):
        ce = walls["ce_walls"]
        pe = walls["pe_walls"]
        ce_str = ", ".join([f"{w['strike']} (OI: {w['oi']:,})" for w in ce])
        pe_str = ", ".join([f"{w['strike']} (OI: {w['oi']:,})" for w in pe])
        context = (
            f"[LIVE OI DATA] {symbol} — Spot: {walls['spot']:,.2f}, "
            f"Expiry: {walls.get('expiry', 'N/A')}, PCR: {walls['pcr']:.2f}\n"
            f"CE Walls (Resistance): {ce_str}\n"
            f"PE Walls (Support): {pe_str}\n\n"
            f"Iske basis pe VRAI analysis do. Exact strikes use karo."
        )
    else:
        context = (
            f"[NOTE] NSE option chain data abhi available nahi hai (API blocked). "
            f"NIFTY current price: {spot:,.2f}. "
            f"Kripya specific OI strike levels mat batao — "
            f"sirf current price pe general analysis do aur clearly bolo "
            f"ki OI data unavailable hai aaj."
        )

    return {"context": context, "has_oi_data": bool(walls and walls.get("ce_walls"))}


@app.get("/market/fii-dii")
async def get_fii_dii():
    """Get latest FII/DII data"""
    from data.market_data import fetcher
    return fetcher.get_fii_dii_data()


# ============================================
# ENTRY POINT
# ============================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
