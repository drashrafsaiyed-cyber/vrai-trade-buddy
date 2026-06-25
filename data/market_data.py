"""
VRAI Trade Buddy — Market Data
Fetches live data from NSE public APIs and Groww Trade API (option chain).
"""

import hashlib
import os
import requests
import time
import uuid
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional

_IST = ZoneInfo("Asia/Kolkata")

# NSE public endpoints (no auth needed)
NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com"
}

# Groww Trade API
GROWW_API_BASE = "https://api.groww.in/v1"
GROWW_TOKEN_URL = f"{GROWW_API_BASE}/token/api/access"


class MarketDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._init_session()

    def _init_session(self):
        """Warm up NSE session with a lightweight API call"""
        try:
            self.session.get(f"{NSE_BASE}/api/marketStatus", timeout=10)
        except Exception as e:
            print(f"[WARN] NSE session init failed: {e}")

    def get_index_quote(self, index: str = "NIFTY 50") -> dict:
        """Get live index quote"""
        try:
            url = f"{NSE_BASE}/api/allIndices"
            r = self.session.get(url, timeout=10)
            data = r.json()
            for item in data.get("data", []):
                if item.get("indexSymbol") == index:
                    return {
                        "symbol": index,
                        "last": item.get("last"),
                        "change": item.get("variation"),
                        "pchange": item.get("percentChange"),
                        "high": item.get("high"),
                        "low": item.get("low"),
                        "open": item.get("open"),
                        "prev_close": item.get("previousClose"),
                        "timestamp": datetime.now(_IST).strftime("%H:%M:%S")
                    }
        except Exception as e:
            print(f"[ERROR] Index quote failed: {e}")

    def get_all_indices(self) -> list:
        """Get ALL Indian indices from NSE in one call — no filter."""
        try:
            url = f"{NSE_BASE}/api/allIndices"
            r = self.session.get(url, timeout=10)
            data = r.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "symbol": item.get("indexSymbol"),
                    "last": item.get("last"),
                    "open": item.get("open"),
                    "pchange": item.get("percentChange"),
                    "change": item.get("variation"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                })
            return results
        except Exception as e:
            print(f"[ERROR] All indices failed: {e}")
            return []

    def get_stock_quote(self, ticker: str) -> dict:
        """Get live stock price for any NSE stock via Yahoo Finance history."""
        try:
            import yfinance as yf
            t = yf.Ticker(f"{ticker}.NS")
            hist = t.history(period="2d", interval="1d")
            if hist.empty:
                return {}
            today = hist.iloc[-1]
            prev_close = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else float(today["Open"])
            price = round(float(today["Close"]), 2)
            return {
                "symbol": ticker,
                "price": price,
                "prev_close": round(prev_close, 2),
                "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close else 0,
                "high": round(float(today["High"]), 2),
                "low": round(float(today["Low"]), 2),
            }
        except Exception as e:
            print(f"[ERROR] Stock quote {ticker} failed: {e}")
            return {}

    def get_sensex(self) -> dict:
        """Fetch SENSEX (BSE) via Yahoo Finance history — more accurate than fast_info."""
        try:
            import yfinance as yf
            t = yf.Ticker("^BSESN")
            hist = t.history(period="2d", interval="1d")
            if hist.empty:
                return {}
            today = hist.iloc[-1]
            prev_close = hist.iloc[-2]["Close"] if len(hist) >= 2 else today["Open"]
            price = round(float(today["Close"]), 2)
            open_p = round(float(today["Open"]), 2)
            high = round(float(today["High"]), 2)
            low = round(float(today["Low"]), 2)
            chg = round(price - prev_close, 2)
            pchg = round(chg / prev_close * 100, 2) if prev_close else 0
            return {
                "symbol": "S&P BSE SENSEX",
                "last": price,
                "open": open_p,
                "high": high,
                "low": low,
                "pchange": pchg,
                "change": chg,
            }
        except Exception as e:
            print(f"[ERROR] SENSEX fetch failed: {e}")
            return {}

    def build_market_context(self, extra_stocks: list = None) -> str:
        """
        Build a rich [LIVE DATA] context string for AI injection.
        Includes all indices + FII/DII + optional specific stocks.
        """
        lines = [f"[LIVE MARKET DATA — {datetime.now(_IST).strftime('%d %b %Y %H:%M')} IST]"]

        # All indices — grouped
        indices = self.get_all_indices()
        # Inject SENSEX from Yahoo Finance (BSE index, not on NSE API)
        sensex = self.get_sensex()
        if sensex:
            indices = [sensex] + [i for i in indices if i.get("symbol") != "S&P BSE SENSEX"]

        if indices:
            # Priority order for display
            priority = [
                "NIFTY 50", "S&P BSE SENSEX", "NIFTY BANK", "NIFTY FIN SERVICE",
                "NIFTY MIDCAP 100", "NIFTY NEXT 50", "INDIA VIX",
                "NIFTY IT", "NIFTY PHARMA", "NIFTY AUTO", "NIFTY FMCG",
                "NIFTY METAL", "NIFTY REALTY", "NIFTY ENERGY", "NIFTY INFRA",
                "NIFTY SMALLCAP 100", "NIFTY MIDCAP 50", "NIFTY 100",
                "NIFTY 200", "NIFTY 500", "NIFTY PSU BANK", "NIFTY PRIVATE BANK",
                "NIFTY HEALTHCARE", "NIFTY CONSUMPTION", "NIFTY COMMODITIES",
                "NIFTY MEDIA", "NIFTY OIL & GAS", "NIFTY INDIA DEFENCE",
            ]
            idx_map = {i["symbol"]: i for i in indices if i["symbol"]}
            ordered = [idx_map[s] for s in priority if s in idx_map]
            rest = [i for i in indices if i["symbol"] not in priority and i["symbol"]]
            ordered += rest

            lines.append("\nINDICES:")
            for idx in ordered:
                arrow = "+" if (idx["pchange"] or 0) >= 0 else ""
                lines.append(
                    f"  {idx['symbol']}: {idx['last']} ({arrow}{idx['pchange']:.2f}%) "
                    f"O:{idx.get('open','-')} H:{idx.get('high','-')} L:{idx.get('low','-')}"
                )

        # FII/DII
        fii = self.get_fii_dii_data()
        if fii and fii.get("date"):
            lines.append(f"\nFII/DII ({fii['date']}):")
            lines.append(f"  FII Net: {fii['fii_net']:+,.0f} Cr | DII Net: {fii['dii_net']:+,.0f} Cr")

        # Extra stocks if requested
        if extra_stocks:
            lines.append("\nSTOCKS:")
            for sym in extra_stocks:
                q = self.get_stock_quote(sym)
                if q:
                    lines.append(
                        f"  {sym}: ₹{q['price']} ({q['change_pct']:+.2f}%) "
                        f"H:{q['high']} L:{q['low']}"
                    )

        return "\n".join(lines)
        return {}

    def get_option_chain(self, symbol: str = "NIFTY") -> dict:
        """
        Get full option chain with OI data.
        Tries NSE direct API first, falls back to curl-based fetch (bypasses Akamai).
        """
        if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]:
            url = f"{NSE_BASE}/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"{NSE_BASE}/api/option-chain-equities?symbol={symbol}"

        data = self._fetch_nse_json(url)
        if not data:
            return {}

        try:
            records = data.get("records", {})
            filtered = data.get("filtered", {})
            return {
                "symbol": symbol,
                "expiry_dates": records.get("expiryDates", []),
                "spot_price": records.get("underlyingValue", 0),
                "timestamp": records.get("timestamp", ""),
                "pcr": filtered.get("PE", {}).get("totOI", 0) / max(filtered.get("CE", {}).get("totOI", 1), 1),
                "total_ce_oi": filtered.get("CE", {}).get("totOI", 0),
                "total_pe_oi": filtered.get("PE", {}).get("totOI", 0),
                "data": records.get("data", [])
            }
        except Exception as e:
            print(f"[ERROR] Option chain parse failed for {symbol}: {e}")
            return {}

    def _fetch_nse_json(self, url: str) -> dict:
        """
        Fetch NSE JSON with Akamai bypass.
        Strategy: warm session with homepage + option-chain page, then call API.
        Falls back to curl subprocess if requests is blocked.
        """
        import subprocess, json as _json

        # Strategy 1: requests session (works on some IPs)
        try:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            })
            s.get(NSE_BASE, timeout=10)
            s.get(f"{NSE_BASE}/option-chain", timeout=10)
            r = s.get(url, timeout=15, headers={"Accept": "application/json"})
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r.json()
        except Exception:
            pass

        # Strategy 2: curl subprocess with cookie jar (handles Akamai JS challenge better)
        try:
            import tempfile, os
            cookie_file = os.path.join(tempfile.gettempdir(), "nse_cookies.txt")
            curl_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

            subprocess.run(
                ["curl", "-s", "-c", cookie_file, "-b", cookie_file,
                 "-A", curl_ua, "-L", "--max-time", "10",
                 NSE_BASE],
                capture_output=True, timeout=12
            )
            subprocess.run(
                ["curl", "-s", "-c", cookie_file, "-b", cookie_file,
                 "-A", curl_ua, "-L", "--max-time", "10",
                 f"{NSE_BASE}/option-chain"],
                capture_output=True, timeout=12
            )
            result = subprocess.run(
                ["curl", "-s", "-c", cookie_file, "-b", cookie_file,
                 "-A", curl_ua,
                 "-H", "Accept: application/json",
                 "-H", f"Referer: {NSE_BASE}/option-chain",
                 "--max-time", "15", url],
                capture_output=True, timeout=18
            )
            text = result.stdout.decode("utf-8", errors="replace").strip()
            if text.startswith("{"):
                return _json.loads(text)
        except Exception as e:
            print(f"[ERROR] Option chain failed for curl fallback: {e}")

        return {}

    def find_oi_walls(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        """
        Find major OI walls — CE resistance and PE support.
        Tries Groww Trade API first (authenticated, not Akamai-blocked),
        falls back to NSE direct API.
        Returns top 3 CE walls and top 3 PE walls.
        """
        # Try Groww first — authenticated, bypasses Akamai
        chain = groww.get_option_chain(underlying=symbol, expiry_date=expiry)
        if not chain:
            chain = self.get_option_chain(symbol)
        if not chain or not chain.get("data"):
            return {}

        spot = chain.get("spot_price", 0)
        expiry_dates = chain.get("expiry_dates", [])
        target_expiry = expiry or (expiry_dates[0] if expiry_dates else None)

        ce_strikes = {}
        pe_strikes = {}

        for record in chain["data"]:
            if target_expiry and record.get("expiryDate") != target_expiry:
                continue

            strike = record.get("strikePrice", 0)

            # CE data
            ce = record.get("CE", {})
            if ce and ce.get("openInterest"):
                ce_strikes[strike] = {
                    "oi": ce.get("openInterest", 0),
                    "change_oi": ce.get("changeinOpenInterest", 0),
                    "ltp": ce.get("lastPrice", 0),
                    "iv": ce.get("impliedVolatility", 0)
                }

            # PE data
            pe = record.get("PE", {})
            if pe and pe.get("openInterest"):
                pe_strikes[strike] = {
                    "oi": pe.get("openInterest", 0),
                    "change_oi": pe.get("changeinOpenInterest", 0),
                    "ltp": pe.get("lastPrice", 0),
                    "iv": pe.get("impliedVolatility", 0)
                }

        # Sort by OI — highest = wall
        top_ce_walls = sorted(
            [(k, v) for k, v in ce_strikes.items() if k > spot],
            key=lambda x: x[1]["oi"],
            reverse=True
        )[:3]

        top_pe_walls = sorted(
            [(k, v) for k, v in pe_strikes.items() if k < spot],
            key=lambda x: x[1]["oi"],
            reverse=True
        )[:3]

        return {
            "symbol": symbol,
            "spot": spot,
            "expiry": target_expiry,
            "pcr": chain.get("pcr", 0),
            "ce_walls": [{"strike": k, **v} for k, v in top_ce_walls],
            "pe_walls": [{"strike": k, **v} for k, v in top_pe_walls],
            "atm_strike": round(spot / 50) * 50  # Round to nearest 50
        }

    def get_vix(self) -> float:
        """Get India VIX"""
        try:
            quote = self.get_index_quote("INDIA VIX")
            return float(quote.get("last", 0))
        except:
            return 0.0

    def get_top_fno_movers(self) -> dict:
        """Get top F&O stocks by OI change — for BTST scanning"""
        try:
            url = f"{NSE_BASE}/api/live-analysis-oi-spurts-underlyings"
            r = self.session.get(url, timeout=10)
            data = r.json()
            return {
                "oi_gainers": data.get("data", [])[:10],
                "timestamp": datetime.now(_IST).strftime("%H:%M:%S")
            }
        except Exception as e:
            print(f"[ERROR] FnO movers failed: {e}")
            return {}

    def get_gift_nifty(self) -> dict:
        """Get Gift Nifty from NSE SGX data"""
        try:
            url = f"{NSE_BASE}/api/marketStatus"
            r = self.session.get(url, timeout=10)
            data = r.json()
            # Extract SGX Nifty if available
            for market in data.get("marketState", []):
                if "GIFT" in market.get("market", "").upper() or "SGX" in market.get("market", "").upper():
                    return {
                        "price": market.get("index", 0),
                        "change": market.get("variation", 0),
                        "pchange": market.get("percentChange", 0)
                    }
        except Exception as e:
            print(f"[ERROR] Gift Nifty failed: {e}")
        return {}

    def get_fii_dii_data(self) -> dict:
        """Get latest FII/DII cash flow data"""
        try:
            url = f"{NSE_BASE}/api/fiidiiTradeReact"
            r = self.session.get(url, timeout=10)
            data = r.json()
            if data and len(data) > 0:
                fii = next((x for x in data if "FII" in x.get("category", "")), {})
                dii = next((x for x in data if "DII" in x.get("category", "")), {})
                date = (fii or dii).get("date", "")
                return {
                    "date": date,
                    "fii_buy": float(fii.get("buyValue", 0)),
                    "fii_sell": float(fii.get("sellValue", 0)),
                    "fii_net": float(fii.get("netValue", 0)),
                    "dii_buy": float(dii.get("buyValue", 0)),
                    "dii_sell": float(dii.get("sellValue", 0)),
                    "dii_net": float(dii.get("netValue", 0))
                }
        except Exception as e:
            print(f"[ERROR] FII/DII data failed: {e}")
        return {}


class GrowwDataFetcher:
    """
    Fetches option chain / OI data from Groww Trade API.
    Handles daily access token refresh (tokens expire at 6 AM IST).
    Auth flow: SHA256(secret + timestamp) → POST /v1/token/api/access → access_token
    Then: GET /v1/option-chain/exchange/NSE/underlying/NIFTY?expiry_date=YYYY-MM-DD
    """

    def __init__(self):
        self.api_key = os.getenv("GROWW_API_KEY", "")      # long-lived JWT from Groww dashboard
        self.secret = os.getenv("GROWW_API_SECRET", "")    # API secret for checksum generation
        self._access_token: Optional[str] = None
        self._token_date: Optional[str] = None             # date string when token was fetched

    def _groww_headers(self, token: str) -> dict:
        return {
            "x-request-id": str(uuid.uuid4()),
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "x-client-id": "growwapi",
            "x-client-platform": "growwapi-python-client",
            "x-client-platform-version": "1.5.0",
            "x-api-version": "1.0",
        }

    def _refresh_access_token(self) -> Optional[str]:
        """Generate a new daily access token using API key + secret checksum."""
        if not self.api_key or not self.secret:
            print("[GROWW] GROWW_API_KEY or GROWW_API_SECRET not set")
            return None
        try:
            timestamp = int(time.time())
            checksum = hashlib.sha256((self.secret + str(timestamp)).encode()).hexdigest()
            headers = self._groww_headers(self.api_key)
            payload = {"key_type": "approval", "checksum": checksum, "timestamp": timestamp}
            r = requests.post(GROWW_TOKEN_URL, headers=headers, json=payload, timeout=15)
            if r.ok:
                token = r.json().get("token")
                if token:
                    print("[GROWW] Access token refreshed successfully")
                    return token
            print(f"[GROWW] Token refresh failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[GROWW] Token refresh error: {e}")
        return None

    def _get_token(self) -> Optional[str]:
        """Return cached token or refresh if stale (new day)."""
        today = date.today().isoformat()
        if self._access_token and self._token_date == today:
            return self._access_token
        token = self._refresh_access_token()
        if token:
            self._access_token = token
            self._token_date = today
        return token

    def get_nearest_expiry(self, exchange: str = "NSE", symbol: str = "NIFTY") -> Optional[str]:
        """Fetch nearest expiry date for a symbol from Groww."""
        token = self._get_token()
        if not token:
            return None
        try:
            url = f"{GROWW_API_BASE}/historical/expiries"
            params = {"exchange": exchange, "underlying_symbol": symbol}
            r = requests.get(url, headers=self._groww_headers(token), params=params, timeout=10)
            if r.ok:
                data = r.json()
                payload = data.get("payload", data)
                expiries = payload if isinstance(payload, list) else payload.get("expiries", [])
                if expiries:
                    return expiries[0]  # nearest expiry
        except Exception as e:
            print(f"[GROWW] Expiry fetch error: {e}")
        return None

    def get_option_chain(self, exchange: str = "NSE", underlying: str = "NIFTY",
                         expiry_date: Optional[str] = None) -> dict:
        """
        Fetch full option chain with OI data from Groww Trade API.
        Returns data in same format expected by find_oi_walls().
        """
        token = self._get_token()
        if not token:
            return {}

        # Get nearest expiry if not specified
        if not expiry_date:
            expiry_date = self.get_nearest_expiry(exchange, underlying)
        if not expiry_date:
            print("[GROWW] Could not determine expiry date")
            return {}

        try:
            url = f"{GROWW_API_BASE}/option-chain/exchange/{exchange}/underlying/{underlying}"
            params = {"expiry_date": expiry_date}
            r = requests.get(url, headers=self._groww_headers(token), params=params, timeout=15)
            if not r.ok:
                print(f"[GROWW] Option chain failed: {r.status_code} {r.text[:200]}")
                return {}

            raw = r.json()
            payload = raw.get("payload", raw)

            # Parse Groww option chain format into NSE-compatible format
            spot = float(payload.get("underlying_value") or payload.get("spot") or 0)
            chain_data = payload.get("data", payload.get("option_chain", []))

            # Build NSE-compatible records list
            records = []
            for item in chain_data:
                strike = float(item.get("strike_price") or item.get("strike") or 0)
                ce = item.get("CE") or item.get("ce") or {}
                pe = item.get("PE") or item.get("pe") or {}

                record = {"strikePrice": strike, "expiryDate": expiry_date}
                if ce:
                    record["CE"] = {
                        "openInterest": ce.get("open_interest") or ce.get("openInterest") or 0,
                        "changeinOpenInterest": ce.get("change_in_oi") or ce.get("changeinOpenInterest") or 0,
                        "lastPrice": ce.get("last_price") or ce.get("ltp") or 0,
                        "impliedVolatility": ce.get("implied_volatility") or ce.get("iv") or 0,
                    }
                if pe:
                    record["PE"] = {
                        "openInterest": pe.get("open_interest") or pe.get("openInterest") or 0,
                        "changeinOpenInterest": pe.get("change_in_oi") or pe.get("changeinOpenInterest") or 0,
                        "lastPrice": pe.get("last_price") or pe.get("ltp") or 0,
                        "impliedVolatility": pe.get("implied_volatility") or pe.get("iv") or 0,
                    }
                records.append(record)

            total_ce_oi = sum(r.get("CE", {}).get("openInterest", 0) for r in records)
            total_pe_oi = sum(r.get("PE", {}).get("openInterest", 0) for r in records)
            pcr = total_pe_oi / max(total_ce_oi, 1)

            print(f"[GROWW] Option chain OK: {len(records)} strikes, spot={spot}, expiry={expiry_date}")
            return {
                "symbol": underlying,
                "expiry_dates": [expiry_date],
                "spot_price": spot,
                "timestamp": datetime.now(_IST).strftime("%H:%M:%S"),
                "pcr": pcr,
                "total_ce_oi": total_ce_oi,
                "total_pe_oi": total_pe_oi,
                "data": records,
            }
        except Exception as e:
            print(f"[GROWW] Option chain parse error: {e}")
            return {}


# Global fetcher instance
fetcher = MarketDataFetcher()

# Global Groww fetcher (for option chain / OI walls)
groww = GrowwDataFetcher()
