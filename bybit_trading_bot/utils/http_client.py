from __future__ import annotations

import hashlib
import hmac
import json
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests

from bybit_trading_bot.utils.logger import get_logger


class RateLimitedHTTP:
    """Thin wrapper over pybit HTTP client with token-bucket rate limiting and backoff.

    - Limits average request rate (token bucket)
    - Retries on transient/rate-limit errors with exponential backoff and jitter
    - Logs rate events
    """

    def __init__(
        self,
        http_client: Any,
        max_requests: int = 120,
        per_seconds: float = 1.0,
        max_retries: int = 5,
        base_backoff: float = 0.2,
        backoff_cap: float = 3.0,
    ) -> None:
        self.http = http_client
        self.logger = get_logger(self.__class__.__name__)

        # Token bucket
        self.capacity = float(max_requests)
        self.tokens = float(max_requests)
        self.refill_rate = float(max_requests) / float(per_seconds)
        self.last_refill = time.time()
        self._lock = threading.Lock()

        # Backoff
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.backoff_cap = backoff_cap

    # ---- Rate limiting ----
    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + elapsed * (self.refill_rate))
        self.last_refill = now

    def _acquire_token(self) -> None:
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # Not enough tokens; compute sleep until 1 token available
                needed = 1.0 - self.tokens
                sleep_time = max(needed / self.refill_rate, 0.005)
            time.sleep(sleep_time)

    # ---- Backoff + request ----
    def _should_retry(self, resp: Any, err: Optional[Exception]) -> bool:
        if err is not None:
            msg = str(err).lower()
            return (
                "429" in msg
                or "rate" in msg
                or "limit" in msg
                or "timeout" in msg
                or "temporarily" in msg
            )
        if isinstance(resp, dict):
            code = resp.get("retCode")
            if code is None:
                return False
            try:
                code = int(code)
            except Exception:
                return False
            # Heuristic: non-zero retCode can be retried for transient cases
            return code != 0
        return False

    def request(self, method_name: str, **kwargs) -> Any:
        attempt = 0
        while True:
            self._acquire_token()
            err: Optional[Exception] = None
            resp = None
            try:
                method: Callable[..., Any] = getattr(self.http, method_name)
                resp = method(**kwargs)
            except Exception as e:  # pybit FailedRequestError or network issues
                err = e

            # Success
            if err is None and isinstance(resp, dict) and int(resp.get("retCode", -1)) == 0:
                return resp

            # Retry?
            if attempt >= self.max_retries or not self._should_retry(resp, err):
                if err is not None:
                    raise err
                return resp

            # Backoff with jitter
            backoff = min(self.backoff_cap, self.base_backoff * (2 ** attempt))
            backoff *= 0.5 + random.random()  # jitter 0.5x..1.5x
            self.logger.warning(
                f"Rate/backoff: method={method_name} attempt={attempt+1} sleeping={backoff:.2f}s"
            )
            time.sleep(backoff)
            attempt += 1 


# ---- MEXC REST adapter with Bybit-like method names ----

@dataclass
class _MexcConfig:
    api_key: str
    api_secret: str
    spot_base: str = "https://api.mexc.com"
    futures_base: str = "https://contract.mexc.com"


class MEXCHTTP:
    """Minimal MEXC client that exposes a subset of Bybit-unified method names.

    Methods implemented to satisfy this project calls:
    - get_instruments_info(category, symbol=None, cursor=None)
    - get_wallet_balance(accountType="UNIFIED")
    - place_order(...)
    - get_order_history(...)
    - get_open_orders(...)
    - cancel_order(...)
    - get_open_interest(...)
    - get_tickers(...)
    """

    def __init__(self, api_key: str | None, api_secret: str | None) -> None:
        self.cfg = _MexcConfig(api_key=api_key or "", api_secret=api_secret or "")
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        if self.cfg.api_key:
            self.session.headers.update({"X-MEXC-APIKEY": self.cfg.api_key})

    # --- Helpers ---
    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        # MEXC: timestamp & signature via HMAC-SHA256 of query string
        p = dict(params)
        p.setdefault("timestamp", int(time.time() * 1000))
        # recvWindow optional
        if "recvWindow" not in p:
            p["recvWindow"] = 5000
        query = "&".join(f"{k}={p[k]}" for k in sorted(p))
        sig = hmac.new(self.cfg.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        p["signature"] = sig
        return p

    def _get(self, url: str, params: Optional[dict[str, Any]] = None, signed: bool = False) -> Any:
        try:
            prms = dict(params or {})
            if signed:
                prms = self._sign(prms)
            resp = self.session.get(url, params=prms, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            return {"retCode": -1, "retMsg": str(e)}

    def _post(self, url: str, params: Optional[dict[str, Any]] = None, signed: bool = True) -> Any:
        try:
            prms = dict(params or {})
            if signed:
                prms = self._sign(prms)
            # MEXC uses application/x-www-form-urlencoded
            resp = self.session.post(url, data=prms, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            return {"retCode": -1, "retMsg": str(e)}

    def _delete(self, url: str, params: Optional[dict[str, Any]] = None, signed: bool = True) -> Any:
        try:
            prms = dict(params or {})
            if signed:
                prms = self._sign(prms)
            resp = self.session.delete(url, params=prms, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            return {"retCode": -1, "retMsg": str(e)}

    # --- Bybit-like methods ---
    def get_instruments_info(self, category: str, symbol: Optional[str] = None, cursor: Optional[str] = None) -> Any:
        if category == "spot":
            url = f"{self.cfg.spot_base}/api/v3/exchangeInfo"
            data = self._get(url)
            symbols = data.get("symbols", []) if isinstance(data, dict) else []
            out_list: list[dict[str, Any]] = []
            for it in symbols:
                if symbol and str(it.get("symbol")) != symbol:
                    continue
                # map filters
                lot = {"basePrecision": it.get("baseAssetPrecision", 6), "quotePrecision": it.get("quotePrecision", 8), "minOrderQty": 0, "minOrderAmt": 0, "qtyStep": 0}
                price_filter = {"tickSize": 0}
                try:
                    for f in it.get("filters", []):
                        if f.get("filterType") == "LOT_SIZE":
                            lot["minOrderQty"] = f.get("minQty", 0)
                            lot["qtyStep"] = f.get("stepSize", 0)
                        elif f.get("filterType") == "NOTIONAL":
                            lot["minOrderAmt"] = f.get("minNotional", 0)
                        elif f.get("filterType") == "PRICE_FILTER":
                            price_filter["tickSize"] = f.get("tickSize", 0)
                except Exception:
                    pass
                out_list.append({
                    "symbol": it.get("symbol"),
                    "baseCoin": it.get("baseAsset"),
                    "lotSizeFilter": lot,
                    "priceFilter": price_filter,
                })
            return {"retCode": 0, "result": {"list": out_list}}
        # Futures list: best-effort
        url = f"{self.cfg.futures_base}/api/v1/contract/detail"
        data = self._get(url)
        items = data.get("data", []) if isinstance(data, dict) else []
        out_list: list[dict[str, Any]] = []
        for it in items:
            sym = it.get("symbol") or it.get("contractCode")
            # Normalize to spot-like symbol (e.g., BTC_USDT -> BTCUSDT)
            if isinstance(sym, str):
                sym = sym.replace("_", "")
            if symbol and sym != symbol:
                continue
            out_list.append({"symbol": sym})
        return {"retCode": 0, "result": {"list": out_list}}

    def get_wallet_balance(self, accountType: str = "UNIFIED") -> Any:  # noqa: N803 - keep signature
        # Map to spot account balances
        url = f"{self.cfg.spot_base}/api/v3/account"
        data = self._get(url, signed=True)
        if isinstance(data, dict) and data.get("retCode", 0) != -1:
            coins = []
            for b in data.get("balances", []):
                coins.append({
                    "coin": b.get("asset"),
                    "availableToTrade": b.get("free"),
                    "availableToWithdraw": b.get("free"),
                    "walletBalance": b.get("free"),
                })
            return {"retCode": 0, "result": {"list": [{"coin": coins}]}}
        return data

    def place_order(self, category: str, symbol: str, side: str, orderType: str, qty: str, price: Optional[str] = None, timeInForce: Optional[str] = None, marketUnit: Optional[str] = None, triggerPrice: Optional[str] = None, triggerDirection: Optional[int] = None, isPostOnly: Optional[bool] = None, tpslMode: Optional[str] = None) -> Any:
        if category != "spot":
            return {"retCode": -1, "retMsg": "Only spot supported in this adapter"}
        url = f"{self.cfg.spot_base}/api/v3/order"
        params: dict[str, Any] = {"symbol": symbol, "side": side.upper(), "type": orderType.upper()}
        if orderType.lower() == "market":
            if marketUnit == "quoteCoin":
                params["quoteOrderQty"] = qty
            else:
                params["quantity"] = qty
        else:
            if price is not None:
                params["price"] = price
            if isPostOnly:
                # MEXC supports timeInForce=PO for post-only
                params["timeInForce"] = "PO"
            elif timeInForce:
                params["timeInForce"] = timeInForce
            params["quantity"] = qty
        return self._post(url, params, signed=True)

    def get_open_orders(self, category: str = "spot", symbol: Optional[str] = None) -> Any:
        url = f"{self.cfg.spot_base}/api/v3/openOrders"
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        data = self._get(url, params, signed=True)
        if isinstance(data, list):
            # Wrap into Bybit-like structure
            return {"retCode": 0, "result": {"list": data}}
        return data

    def cancel_order(self, category: str, symbol: str, orderId: str) -> Any:  # noqa: N803
        url = f"{self.cfg.spot_base}/api/v3/order"
        params = {"symbol": symbol, "orderId": orderId}
        return self._delete(url, params, signed=True)

    def get_order_history(self, category: str, orderId: Optional[str] = None, symbol: Optional[str] = None) -> Any:  # noqa: N803
        # Prefer single order endpoint when id provided; else use allOrders
        if orderId and symbol:
            url = f"{self.cfg.spot_base}/api/v3/order"
            data = self._get(url, {"symbol": symbol, "orderId": orderId}, signed=True)
            if isinstance(data, dict) and data.get("orderId"):
                return {"retCode": 0, "result": {"list": [data]}}
        url = f"{self.cfg.spot_base}/api/v3/allOrders"
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        data = self._get(url, params, signed=True)
        if isinstance(data, list):
            return {"retCode": 0, "result": {"list": data}}
        return data

    # Futures-like helpers (best-effort)
    def get_open_interest(self, category: str, symbol: str, intervalTime: str = "5min") -> Any:  # noqa: N803
        # Try MEXC futures OI endpoint (if available); otherwise return not supported
        url = f"{self.cfg.futures_base}/api/v1/contract/open_interest"
        data = self._get(url, {"symbol": symbol, "interval": intervalTime})
        # Expect data format may vary; attempt to normalize into list with openInterest/openInterestValue
        rows = []
        try:
            lst = data.get("data") or data.get("result") or []
            for r in lst[-10:]:
                rows.append({
                    "openInterest": r.get("openInterest") or r.get("oi"),
                    "openInterestValue": r.get("openInterestValue") or r.get("oiValue"),
                })
        except Exception:
            rows = []
        if rows:
            return {"retCode": 0, "result": {"list": rows}}
        # fallback none
        return {"retCode": 0, "result": {"list": []}}

    def get_tickers(self, category: str, symbol: str) -> Any:
        if category == "linear":
            # Fallback to spot last price as approximation
            url = f"{self.cfg.spot_base}/api/v3/ticker/price"
            data = self._get(url, {"symbol": symbol})
            if isinstance(data, dict) and data.get("price") is not None:
                return {"retCode": 0, "result": {"list": [{"lastPrice": data.get("price")}]}}
            return {"retCode": 0, "result": {"list": []}}
        url = f"{self.cfg.spot_base}/api/v3/ticker/price"
        return self._get(url, {"symbol": symbol})