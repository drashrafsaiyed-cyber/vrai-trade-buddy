"""
VRAI Trade Buddy — Two-way Telegram Bot
Receives messages, responds with AI + live market data.
Supports trade execution commands via Angel One.
"""

import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))


def _is_authorized(update: Update) -> bool:
    return update.effective_chat.id == CHAT_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message — respond with AI + live data."""
    if not _is_authorized(update):
        return

    user_msg = update.message.text.strip()
    await update.message.reply_text("Dekh raha hoon... ek second.", quote=False)

    try:
        from data.market_data import fetcher
        from core.brain import brain
        from main import _extract_stock_mentions

        # Detect stock mentions + build full market context
        stocks = _extract_stock_mentions(user_msg)
        context = fetcher.build_market_context(extra_stocks=stocks)
        enriched = context + "\n\nUser: " + user_msg

        response = brain.chat(enriched)
        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_oi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/oi — Get NIFTY OI walls from Angel One."""
    if not _is_authorized(update):
        return

    await update.message.reply_text("OI walls fetch kar raha hoon...")
    try:
        from data.market_data import fetcher
        from data.angel_one import angel

        nifty = fetcher.get_index_quote("NIFTY 50")
        spot = nifty.get("last", 24000) if nifty else 24000

        walls = angel.get_option_chain_oi("NIFTY", spot=float(spot))

        if walls and walls.get("ce_walls"):
            ce = walls["ce_walls"]
            pe = walls["pe_walls"]
            ce_str = "\n".join([f"  {w['strike']:.0f} CE — OI: {w['oi']:,}" for w in ce])
            pe_str = "\n".join([f"  {w['strike']:.0f} PE — OI: {w['oi']:,}" for w in pe])
            msg = (
                f"NIFTY OI Walls — {walls['expiry']}\n"
                f"Spot: {spot} | PCR: {walls['pcr']}\n\n"
                f"CE Resistance (Walls):\n{ce_str}\n\n"
                f"PE Support (Walls):\n{pe_str}"
            )
        else:
            msg = f"OI data unavailable. NIFTY: {spot}"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"OI fetch failed: {e}")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/portfolio — Show current F&O positions."""
    if not _is_authorized(update):
        return

    await update.message.reply_text("Positions fetch kar raha hoon...")
    try:
        from data.angel_one import angel
        pos = angel.get_portfolio()
        data = pos.get("data", [])

        if not data:
            await update.message.reply_text("Koi open position nahi hai.")
            return

        lines = ["Open Positions:"]
        total_pnl = 0
        for p in data:
            sym = p.get("tradingsymbol", "")
            qty = p.get("netqty", 0)
            pnl = float(p.get("unrealised", 0))
            total_pnl += pnl
            lines.append(f"  {sym}: Qty {qty}, P&L: {pnl:+,.0f}")

        lines.append(f"\nTotal Unrealised P&L: {total_pnl:+,.0f}")
        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        await update.message.reply_text(f"Portfolio error: {e}")


async def cmd_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/funds — Show available margin."""
    if not _is_authorized(update):
        return

    try:
        from data.angel_one import angel
        funds = angel.get_funds()
        data = funds.get("data", {})
        available = data.get("availablecash", "N/A")
        used = data.get("utiliseddebits", "N/A")
        await update.message.reply_text(
            f"Funds:\n  Available: ₹{available}\n  Used: ₹{used}"
        )
    except Exception as e:
        await update.message.reply_text(f"Funds error: {e}")


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /buy NIFTY 24200 CE 26JUN2026 1
    Place a BUY order.
    """
    if not _is_authorized(update):
        return

    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Format: /buy SYMBOL STRIKE CE/PE EXPIRY [LOTS]\n"
            "Example: /buy NIFTY 24200 CE 26JUN2026 1"
        )
        return

    symbol = args[0].upper()
    strike = float(args[1])
    opt_type = args[2].upper()
    expiry = args[3].upper()
    lots = int(args[4]) if len(args) > 4 else 1

    await update.message.reply_text(
        f"Order place kar raha hoon:\n"
        f"BUY {symbol} {strike:.0f} {opt_type} — {lots} lot(s)"
    )

    try:
        from data.angel_one import angel
        result = angel.place_order(symbol, opt_type, strike, expiry, "BUY", lots)
        if result.get("error"):
            await update.message.reply_text(f"Order failed: {result['error']}")
        else:
            order_id = result.get("data", {}).get("orderid", "Unknown")
            await update.message.reply_text(
                f"Order placed!\n"
                f"Order ID: {order_id}\n"
                f"Remember: Exit by 9:15 AM if BTST!"
            )
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")


async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /sell NIFTY 24200 CE 26JUN2026 1
    Place a SELL order.
    """
    if not _is_authorized(update):
        return

    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Format: /sell SYMBOL STRIKE CE/PE EXPIRY [LOTS]\n"
            "Example: /sell NIFTY 24200 CE 26JUN2026 1"
        )
        return

    symbol = args[0].upper()
    strike = float(args[1])
    opt_type = args[2].upper()
    expiry = args[3].upper()
    lots = int(args[4]) if len(args) > 4 else 1

    await update.message.reply_text(
        f"SELL order place kar raha hoon:\n"
        f"SELL {symbol} {strike:.0f} {opt_type} — {lots} lot(s)"
    )

    try:
        from data.angel_one import angel
        result = angel.place_order(symbol, opt_type, strike, expiry, "SELL", lots)
        if result.get("error"):
            await update.message.reply_text(f"Order failed: {result['error']}")
        else:
            order_id = result.get("data", {}).get("orderid", "Unknown")
            await update.message.reply_text(f"SELL order placed! Order ID: {order_id}")
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")


async def cmd_nifty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/nifty — Quick NIFTY quote."""
    if not _is_authorized(update):
        return
    from data.market_data import fetcher
    nifty = fetcher.get_index_quote("NIFTY 50")
    if nifty:
        await update.message.reply_text(
            f"NIFTY 50: {nifty['last']}\n"
            f"Change: {nifty['change']:+.1f} ({nifty['pchange']:+.2f}%)\n"
            f"High: {nifty['high']} | Low: {nifty['low']}"
        )
    else:
        await update.message.reply_text("NIFTY data unavailable.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — Check Angel One login and system health."""
    if not _is_authorized(update):
        return
    from data.angel_one import angel
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist).strftime("%d %b %Y %H:%M IST")

    # Check Angel One session
    client = angel._get_client()
    if client:
        session_date = angel._session_date or "unknown"
        ao_status = f"Angel One: LOGGED IN (session: {session_date})"
    else:
        ao_status = "Angel One: NOT LOGGED IN — market data & trades down!"

    msg = (
        f"VRAI Trade Buddy Status\n"
        f"Time: {now}\n\n"
        f"{ao_status}\n"
        f"Bot: Running\n"
        f"Scheduler: Active"
    )
    await update.message.reply_text(msg)


async def cmd_relogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/relogin — Force Angel One re-login with fresh TOTP."""
    if not _is_authorized(update):
        return
    await update.message.reply_text("Angel One re-login try kar raha hoon...")
    from data.angel_one import angel
    angel._session_date = None  # Force fresh login
    angel._obj = None
    client = angel._get_client()
    if client:
        await update.message.reply_text(f"Re-login successful! Session: {angel._session_date}")
    else:
        await update.message.reply_text("Re-login FAILED. Render logs check karo ya credentials verify karo.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help — Show all commands."""
    if not _is_authorized(update):
        return
    msg = (
        "VRAI Trade Buddy Commands:\n\n"
        "/nifty — Live NIFTY quote\n"
        "/oi — NIFTY OI walls (Angel One)\n"
        "/portfolio — Open F&O positions\n"
        "/funds — Available margin\n"
        "/buy NIFTY 24200 CE 26JUN2026 1 — Place buy order\n"
        "/sell NIFTY 24200 CE 26JUN2026 1 — Place sell order\n"
        "/status — Check Angel One login & system health\n"
        "/relogin — Force Angel One re-login\n\n"
        "Ya kuch bhi likho — AI se baat karo!"
    )
    await update.message.reply_text(msg)


def build_application() -> Application:
    """Build and return the Telegram Application."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("oi", cmd_oi))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("funds", cmd_funds))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("sell", cmd_sell))
    app.add_handler(CommandHandler("nifty", cmd_nifty))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("relogin", cmd_relogin))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
