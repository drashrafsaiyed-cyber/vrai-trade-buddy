"""
VRAI Trade Buddy — Market Data
Fetches live data from NSE, web sources
No paid API needed — uses public endpoints
"""

import requests
import json
from datetime import datetime
from typing import Optional

# NSE public endpoints (no auth needed)
NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com"
}


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
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
        except Exception as e:
            print(f"[ERROR] Index quote failed: {e}")
        return {}

    def get_option_chain(self, symbol: str = "NIFTY") -> dict:
        """
        Get full option chain with OI data
        Returns CE/PE OI for all strikes
        """
        try:
            if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]:
                url = f"{NSE_BASE}/api/option-chain-indices?symbol={symbol}"
            else:
                url = f"{NSE_BASE}/api/option-chain-equities?symbol={symbol}"

            r = self.session.get(url, timeout=15)
            data = r.json()

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
            print(f"[ERROR] Option chain failed for {symbol}: {e}")
            return {}

    def find_oi_walls(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        """
        Find major OI walls — CE resistance and PE support
        Returns top 3 CE walls and top 3 PE walls
        """
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
                "timestamp": datetime.now().strftime("%H:%M:%S")
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


# Global fetcher instance
fetcher = MarketDataFetcher()
