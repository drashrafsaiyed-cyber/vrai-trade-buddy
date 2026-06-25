"""
VRAI Trade Buddy — Notification Handler
Telegram: Ready (add token tomorrow after ban lifted)
Web fallback: Active now for testing
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ADD_TOMORROW")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "ADD_TOMORROW")

# In-memory notification log (shown in web UI)
notification_log = []


def send_notification(message: str, alert_type: str = "INFO"):
    """
    Master notification function.
    Sends to Telegram if available, logs to web UI always.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Always log for web UI
    notification_log.append({
        "time": timestamp,
        "type": alert_type,
        "message": message
    })

    # Keep only last 50 notifications
    if len(notification_log) > 50:
        notification_log.pop(0)

    print(f"[NOTIFY] [{alert_type}] {timestamp}: {message[:100]}...")

    # Send to Telegram if token is configured
    if TELEGRAM_BOT_TOKEN != "ADD_TOMORROW" and TELEGRAM_CHAT_ID != "ADD_TOMORROW":
        _send_telegram(message)
    else:
        print("[NOTIFY] Telegram not configured yet — logging only (add tomorrow)")


def _send_telegram(message: str):
    """Send message to Telegram"""
    try:
        import requests
        # Split long messages (Telegram limit = 4096 chars)
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML"
            }
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"[ERROR] Telegram send failed: {r.text}")
    except Exception as e:
        print(f"[ERROR] Telegram error: {e}")


def send_morning_brief(message: str):
    send_notification(message, "MORNING_BRIEF")


def send_btst_alert(message: str):
    send_notification(message, "BTST_ALERT")


def send_gamma_blast(message: str):
    send_notification(message, "GAMMA_BLAST")


def send_exit_reminder():
    msg = """
⏰ EXIT REMINDER — 9:15 AM

Agar koi BTST position hai:
→ MARKET ORDER lagao ABHI
→ Koi limit order mat lagao
→ Gap up mile toh bhi exit — greed nahi

"Profits book karo, market dekho baad mein" 💪
""".strip()
    send_notification(msg, "EXIT_REMINDER")


def get_notification_log():
    """Return notification log for web UI"""
    return notification_log
