from __future__ import annotations

from typing import Optional

import os
from bybit_trading_bot.utils.logger import get_logger
from bybit_trading_bot.utils.http_client import RateLimitedHTTP, MEXCHTTP

try:
    from pybit.unified_trading import HTTP
except Exception:  # pragma: no cover
    HTTP = None  # type: ignore


class FuturesHandler:
    def __init__(self, testnet: bool) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self._raw_http = None
        self._http = None
        prefer_mexc = os.getenv("EXCHANGE", "").strip().lower() == "mexc" or bool(os.getenv("MEXC_API_KEY"))
        if prefer_mexc:
            try:
                self._raw_http = MEXCHTTP(os.getenv("MEXC_API_KEY"), os.getenv("MEXC_API_SECRET"))
                self._http = RateLimitedHTTP(self._raw_http, max_requests=90, per_seconds=3.0)
                self.logger.info("FuturesHandler using MEXC HTTP adapter")
            except Exception as e:
                self.logger.error(f"Failed to init MEXC HTTP for futures: {e}")
        if self._http is None and HTTP is not None:
            try:
                self._raw_http = HTTP(testnet=testnet)
                self._http = RateLimitedHTTP(self._raw_http, max_requests=90, per_seconds=3.0)
                self.logger.info("FuturesHandler using Bybit HTTP client")
            except Exception as e:
                self.logger.error(f"Failed to init HTTP for futures: {e}")

    def get_open_interest(self, symbol: str) -> Optional[float]:
        if self._http is None:
            return None
        try:
            resp = self._http.request("get_open_interest", category="linear", symbol=symbol, intervalTime="5min")
            result = resp.get("result", {}) if isinstance(resp, dict) else {}
            rows = result.get("list", []) if isinstance(result, dict) else []
            if not rows:
                return None
            latest = rows[-1]
            # Prefer monetary OI value; return both as tuple-like via encoding string? No: return mon value here.
            oi_val = latest.get("openInterestValue") or latest.get("open_interest_value")
            if oi_val is not None:
                return float(oi_val)
            oi_contracts = latest.get("openInterest") or latest.get("open_interest")
            return float(oi_contracts) if oi_contracts is not None else None
        except Exception as e:
            self.logger.error(f"Failed to fetch OI for {symbol}: {e}")
            return None

    def get_open_interest_contracts(self, symbol: str) -> Optional[float]:
        if self._http is None:
            return None
        try:
            resp = self._http.request("get_open_interest", category="linear", symbol=symbol, intervalTime="5min")
            result = resp.get("result", {}) if isinstance(resp, dict) else {}
            rows = result.get("list", []) if isinstance(result, dict) else []
            if not rows:
                return None
            latest = rows[-1]
            oi_contracts = latest.get("openInterest") or latest.get("open_interest")
            return float(oi_contracts) if oi_contracts is not None else None
        except Exception as e:
            self.logger.error(f"Failed to fetch OI (contracts) for {symbol}: {e}")
            return None

    def get_mark_price(self, symbol: str) -> Optional[float]:
        if self._http is None:
            return None
        try:
            resp = self._http.request("get_tickers", category="linear", symbol=symbol)
            result = resp.get("result", {}) if isinstance(resp, dict) else {}
            rows = result.get("list", []) if isinstance(result, dict) else []
            if not rows:
                return None
            mp = rows[0].get("markPrice") or rows[0].get("lastPrice")
            return float(mp) if mp is not None else None
        except Exception as e:
            self.logger.error(f"Failed to fetch OI/price for {symbol}: {e}")
            return None 