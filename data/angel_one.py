"""
Angel One SmartAPI integration.
Handles: auto-login with TOTP, option chain OI, order placement.
"""

import os
import time
import pyotp
import requests
from datetime import date, datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

INSTRUMENTS_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# Angel One token IDs for major NSE indices
NSE_INDEX_TOKENS = {
    "NIFTY 50":           "99926000",
    "NIFTY BANK":         "99926009",
    "NIFTY FIN SERVICE":  "99926037",
    "NIFTY MIDCAP 100":   "99926011",
    "INDIA VIX":          "99926017",
    "NIFTY IT":           "99926006",
    "NIFTY PHARMA":       "99926013",
    "NIFTY AUTO":         "99926003",
    "NIFTY FMCG":         "99926004",
    "NIFTY METAL":        "99926010",
    "NIFTY REALTY":       "99926014",
    "NIFTY ENERGY":       "99926015",
    "NIFTY 100":          "99926001",
    "NIFTY 200":          "99926002",
    "NIFTY 500":          "99926016",
    "NIFTY SMALLCAP 100": "99926018",
    "NIFTY NEXT 50":      "99926019",
    "NIFTY PSU BANK":     "99926026",
    "NIFTY PRIVATE BANK": "99926024",
    "NIFTY MEDIA":        "99926023",
    "NIFTY OIL & GAS":    "99926036",
    "NIFTY COMMODITIES":  "99926025",
    "NIFTY MIDCAP 50":    "99926028",
    "NIFTY INFRA":        "99926007",
    "NIFTY CONSUMPTION":  "99926030",
}

BSE_INDEX_TOKENS = {
    "S&P BSE SENSEX": "1",
}


class AngelOneManager:
    def __init__(self):
        self.api_key = os.getenv("ANGELONE_API_KEY", "")
        self.client_id = os.getenv("ANGELONE_CLIENT_ID", "")
        self.pin = os.getenv("ANGELONE_PIN", "")
        self.totp_secret = os.getenv("ANGELONE_TOTP_SECRET", "")

        self._obj = None
        self._jwt = None
        self._session_date: Optional[str] = None
        self._instruments = None
        self._instruments_date: Optional[str] = None

    def _notify_telegram(self, message: str):
        """Send urgent message to Telegram — used for login alerts."""
        try:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if not token or not chat_id:
                return
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=5
            )
        except Exception:
            pass

    def _login(self) -> bool:
        if not all([self.api_key, self.client_id, self.pin, self.totp_secret]):
            msg = "ANGEL ONE LOGIN FAILED — Credentials missing in environment variables. Check Render env vars."
            print(f"[ANGEL] {msg}")
            self._notify_telegram(f"Angel One: {msg}")
            return False
        try:
            from SmartApi import SmartConnect
            totp = pyotp.TOTP(self.totp_secret).now()
            obj = SmartConnect(api_key=self.api_key)
            data = obj.generateSession(self.client_id, self.pin, totp)
            if data.get("status"):
                self._obj = obj
                self._jwt = data["data"]["jwtToken"]
                self._session_date = date.today().isoformat()
                print(f"[ANGEL] Login OK — JWT starts: {self._jwt[:30]}...")
                return True
            error_msg = data.get("message", "Unknown error")
            print(f"[ANGEL] Login failed: {error_msg}")
            self._notify_telegram(
                f"Angel One Login FAILED!\n"
                f"Reason: {error_msg}\n"
                f"Market data aur trades kaam nahi karenge.\n"
                f"Angel One app mein check karo — TOTP ya PIN change toh nahi hua?"
            )
        except Exception as e:
            print(f"[ANGEL] Login error: {e}")
            self._notify_telegram(
                f"Angel One Login ERROR!\n"
                f"Error: {str(e)}\n"
                f"Render logs check karo."
            )
        return False

    def _get_client(self):
        today = date.today().isoformat()
        if self._obj and self._session_date == today:
            return self._obj
        if self._login():
            return self._obj
        return None

    def _load_instruments(self) -> list:
        today = date.today().isoformat()
        if self._instruments and self._instruments_date == today:
            return self._instruments
        try:
            r = requests.get(INSTRUMENTS_URL, timeout=30)
            self._instruments = r.json()
            self._instruments_date = today
            print(f"[ANGEL] Instruments loaded: {len(self._instruments)}")
            return self._instruments
        except Exception as e:
            print(f"[ANGEL] Instruments download failed: {e}")
            return []

    def get_option_chain_oi(self, symbol: str = "NIFTY", spot: float = 0) -> dict:
        """
        Fetch CE/PE OI for top 16 strikes around ATM using Angel One market data.
        Returns data in same format as MarketDataFetcher.find_oi_walls().
        """
        client = self._get_client()
        if not client:
            return {}

        instruments = self._load_instruments()
        if not instruments:
            return {}

        # Filter options for this symbol
        opts = [x for x in instruments if
                x.get("name") == symbol and
                x.get("instrumenttype") == "OPTIDX" and
                x.get("exch_seg") == "NFO"]

        if not opts:
            print(f"[ANGEL] No options found for {symbol}")
            return {}

        # Get nearest expiry
        expiries = sorted(set(x["expiry"] for x in opts))
        nearest = expiries[0]

        # Get strikes for nearest expiry
        near_opts = [x for x in opts if x["expiry"] == nearest]
        strikes = sorted(set(float(x["strike"]) / 100 for x in near_opts))

        # Find ATM
        if spot <= 0:
            spot = strikes[len(strikes) // 2]
        atm = min(strikes, key=lambda s: abs(s - spot))
        atm_idx = strikes.index(atm)

        # Select 8 strikes above and below ATM
        selected_strikes = strikes[max(0, atm_idx - 8): atm_idx + 9]

        # Build token list
        tokens = []
        strike_token_map = {}
        for s in selected_strikes:
            for opt in near_opts:
                if float(opt["strike"]) / 100 == s:
                    sym = opt["symbol"]
                    tok = opt["token"]
                    option_type = "CE" if sym.endswith("CE") else "PE"
                    tokens.append({
                        "exchange": "NFO",
                        "tradingsymbol": sym,
                        "symboltoken": tok,
                    })
                    strike_token_map[tok] = {"strike": s, "type": option_type}

        if not tokens:
            return {}

        # Fetch market data in batches of 50
        time.sleep(0.5)
        try:
            result = client.getMarketData("FULL", tokens[:50])
        except Exception as e:
            print(f"[ANGEL] Market data error: {e}")
            return {}

        if not result or not result.get("status"):
            print(f"[ANGEL] Market data failed: {result}")
            return {}

        # Parse OI per strike
        ce_oi = {}
        pe_oi = {}
        fetched = result.get("data", {}).get("fetched", [])

        for item in fetched:
            tok = item.get("symbolToken", "")
            info = strike_token_map.get(tok, {})
            s = info.get("strike", 0)
            oi = item.get("opnInterest", 0) or item.get("openInterest", 0) or 0
            ltp = item.get("ltp", 0)
            if info.get("type") == "CE":
                ce_oi[s] = {"oi": oi, "ltp": ltp}
            elif info.get("type") == "PE":
                pe_oi[s] = {"oi": oi, "ltp": ltp}

        # Find top CE walls (above spot) and PE walls (below spot)
        top_ce = sorted(
            [(s, v) for s, v in ce_oi.items() if s > spot],
            key=lambda x: x[1]["oi"], reverse=True
        )[:3]

        top_pe = sorted(
            [(s, v) for s, v in pe_oi.items() if s < spot],
            key=lambda x: x[1]["oi"], reverse=True
        )[:3]

        total_ce_oi = sum(v["oi"] for v in ce_oi.values())
        total_pe_oi = sum(v["oi"] for v in pe_oi.values())
        pcr = round(total_pe_oi / max(total_ce_oi, 1), 2)

        print(f"[ANGEL] OI walls OK — CE top: {[s for s, _ in top_ce]}, PE top: {[s for s, _ in top_pe]}")

        return {
            "symbol": symbol,
            "spot": spot,
            "expiry": nearest,
            "pcr": pcr,
            "ce_walls": [{"strike": s, "oi": v["oi"], "ltp": v["ltp"]} for s, v in top_ce],
            "pe_walls": [{"strike": s, "oi": v["oi"], "ltp": v["ltp"]} for s, v in top_pe],
            "atm_strike": round(spot / 50) * 50,
        }

    def get_all_index_quotes(self) -> list:
        """
        Fetch OHLC for all major NSE indices + SENSEX via Angel One.
        Returns list of dicts compatible with MarketDataFetcher.get_all_indices().
        """
        client = self._get_client()
        if not client:
            return []
        try:
            exchange_tokens = {
                "NSE": list(NSE_INDEX_TOKENS.values()),
                "BSE": list(BSE_INDEX_TOKENS.values()),
            }
            result = client.getMarketData("OHLC", exchange_tokens)
            if not result or not result.get("status"):
                print(f"[ANGEL] Index quotes failed: {result}")
                return []

            token_to_name = {v: k for k, v in NSE_INDEX_TOKENS.items()}
            token_to_name.update({v: k for k, v in BSE_INDEX_TOKENS.items()})

            quotes = []
            for item in result.get("data", {}).get("fetched", []):
                tok = str(item.get("symbolToken", ""))
                name = token_to_name.get(tok, tok)
                ltp = float(item.get("ltp", 0) or 0)
                prev = float(item.get("close", 0) or ltp)
                chg = round(ltp - prev, 2)
                pchg = round(chg / prev * 100, 2) if prev else 0
                quotes.append({
                    "symbol": name,
                    "last":   ltp,
                    "open":   float(item.get("open", 0) or 0),
                    "high":   float(item.get("high", 0) or 0),
                    "low":    float(item.get("low",  0) or 0),
                    "change": chg,
                    "pchange": pchg,
                })
            print(f"[ANGEL] Index quotes OK — {len(quotes)} indices")
            return quotes
        except Exception as e:
            print(f"[ANGEL] Index quotes error: {e}")
            return []

    def get_stock_quotes(self, symbols: list) -> list:
        """
        Fetch OHLC for a list of NSE stock symbols via Angel One instruments master.
        Returns list of dicts compatible with MarketDataFetcher.get_stock_quote().
        """
        if not symbols:
            return []
        client = self._get_client()
        if not client:
            return []
        instruments = self._load_instruments()
        if not instruments:
            return []

        tokens = []
        tok_sym_map = {}
        for sym in symbols:
            match = next(
                (x for x in instruments
                 if x.get("symbol") == sym
                 and x.get("exch_seg") == "NSE"
                 and x.get("instrumenttype") in ("", "EQ")),
                None
            )
            if match:
                tok = match["token"]
                tokens.append(tok)
                tok_sym_map[tok] = sym

        if not tokens:
            return []
        try:
            result = client.getMarketData("OHLC", {"NSE": tokens})
            if not result or not result.get("status"):
                return []
            quotes = []
            for item in result.get("data", {}).get("fetched", []):
                tok = str(item.get("symbolToken", ""))
                sym = tok_sym_map.get(tok, tok)
                ltp = float(item.get("ltp", 0) or 0)
                prev = float(item.get("close", 0) or ltp)
                chg_pct = round((ltp - prev) / prev * 100, 2) if prev else 0
                quotes.append({
                    "symbol":     sym,
                    "price":      ltp,
                    "prev_close": prev,
                    "change_pct": chg_pct,
                    "high":       float(item.get("high", 0) or 0),
                    "low":        float(item.get("low",  0) or 0),
                    "open":       float(item.get("open", 0) or 0),
                })
            return quotes
        except Exception as e:
            print(f"[ANGEL] Stock quotes error: {e}")
            return []

    def place_order(self, symbol: str, option_type: str, strike: float,
                    expiry_str: str, action: str, quantity: int = 1) -> dict:
        """
        Place a F&O option order via Angel One.
        action: BUY or SELL
        expiry_str: e.g. "26JUN2026"
        Returns order response dict.
        """
        client = self._get_client()
        if not client:
            return {"error": "Not logged in"}

        # Build trading symbol e.g. NIFTY26JUN2426000CE
        strike_int = int(strike)
        trading_symbol = f"{symbol}{expiry_str}{strike_int}{option_type}"

        # Look up token
        instruments = self._load_instruments()
        match = next((x for x in instruments if x.get("symbol") == trading_symbol), None)
        if not match:
            return {"error": f"Symbol {trading_symbol} not found in instruments master"}

        try:
            order = client.placeOrder({
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": match["token"],
                "transactiontype": action,
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "CARRYFORWARD",
                "duration": "DAY",
                "quantity": str(quantity * 75),  # NIFTY lot size = 75
            })
            return order
        except Exception as e:
            return {"error": str(e)}

    def get_portfolio(self) -> dict:
        """Get current positions."""
        client = self._get_client()
        if not client:
            return {}
        try:
            return client.position()
        except Exception as e:
            print(f"[ANGEL] Portfolio error: {e}")
            return {}

    def get_funds(self) -> dict:
        """Get available margin/funds."""
        client = self._get_client()
        if not client:
            return {}
        try:
            return client.rmsLimit()
        except Exception as e:
            print(f"[ANGEL] Funds error: {e}")
            return {}


# Global instance
angel = AngelOneManager()
