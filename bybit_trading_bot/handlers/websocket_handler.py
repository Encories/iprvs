from __future__ import annotations

from typing import Callable, List, Optional

from bybit_trading_bot.utils.logger import get_logger

try:
    from pybit.unified_trading import WebSocket
except Exception:  # pragma: no cover
    WebSocket = None  # type: ignore

import time
import threading
import random


TickerCallback = Callable[[str, float, float], None]
OrderbookCallback = Callable[[str, float, float, list, list], None]
TradeCallback = Callable[[str, float, float, float], None]
TradeCallback = Callable[[str, float, float, float], None]


class WebSocketHandler:
    """Обработка WebSocket соединений для спот-рынка (с авто‑переподключением)."""

    def __init__(self, testnet: bool) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self.testnet = testnet
        self._ws = None
        self._symbols: List[str] = []
        self._on_ticker: Optional[TickerCallback] = None
        self._on_orderbook: Optional[OrderbookCallback] = None
        self._on_trade: Optional[TradeCallback] = None
        self._on_trade: Optional[TradeCallback] = None
        self._last_tick_time: float = 0.0
        self._lock = threading.Lock()

        # Reconnect monitor
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._base_backoff = 1.0
        self._backoff_cap = 30.0
        self._stale_seconds = 15.0  # no ticks for this duration → reconnect

        if WebSocket is not None:
            try:
                self._ws = WebSocket(testnet=self.testnet, channel_type="spot")
            except Exception as e:
                self.logger.error(f"Failed to init WebSocket: {e}")

    def connect_to_spot_stream(self, symbols: List[str], on_ticker: Optional[TickerCallback] = None) -> None:
        """Подключение к потоку спот-данных (тикеры) и запуск мониторинга."""
        if self._ws is None:
            self.logger.warning("WebSocket not available; running in stub mode")
            return
        with self._lock:
            self._symbols = list(symbols)
            self._on_ticker = on_ticker
        try:
            for sym in symbols:
                self._ws.ticker_stream(callback=(lambda msg, s=sym: self._on_raw_ticker(msg, s, on_ticker)), symbol=sym)
            self._last_tick_time = time.time()
            self.logger.info(f"Subscribed to {len(symbols)} spot tickers")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to ticker stream: {e}")
        # Start health monitor once
        if self._monitor_thread is None:
            self._monitor_thread = threading.Thread(target=self._monitor_loop, name="WSMonitor", daemon=True)
            self._monitor_thread.start()

    def subscribe_orderbook_and_trades(
        self,
        symbols: List[str],
        on_orderbook: Optional[OrderbookCallback] = None,
        on_trade: Optional[TradeCallback] = None,
    ) -> None:
        if self._ws is None:
            self.logger.warning("WebSocket not available; running in stub mode (orderbook/trades)")
            return
        with self._lock:
            self._symbols = list(set(self._symbols + list(symbols)))
            self._on_orderbook = on_orderbook
            self._on_trade = on_trade
        try:
            for sym in symbols:
                # Orderbook 50 levels
                try:
                    self._ws.orderbook_stream(callback=(lambda msg, s=sym: self._on_raw_orderbook(msg, s, on_orderbook)), symbol=sym, depth=50)  # type: ignore[attr-defined]
                except Exception:
                    try:
                        self._ws.orderbook_50_stream(callback=(lambda msg, s=sym: self._on_raw_orderbook(msg, s, on_orderbook)), symbol=sym)  # type: ignore[attr-defined]
                    except Exception as e:
                        self.logger.debug(f"Orderbook subscribe not available for {sym}: {e}")
                # Public trades
                try:
                    self._ws.public_trade_stream(callback=(lambda msg, s=sym: self._on_raw_trade(msg, s, on_trade)), symbol=sym)  # type: ignore[attr-defined]
                except Exception as e:
                    self.logger.debug(f"Trade subscribe not available for {sym}: {e}")
            self._last_tick_time = time.time()
            self.logger.info(f"Subscribed orderbook/trades for {len(symbols)} symbols")
        except Exception as e:
            self.logger.error(f"Failed to subscribe orderbook/trades: {e}")
        if self._monitor_thread is None:
            self._monitor_thread = threading.Thread(target=self._monitor_loop, name="WSMonitor", daemon=True)
            self._monitor_thread.start()

    def _on_raw_ticker(self, message, symbol: str, on_ticker: Optional[TickerCallback]) -> None:
        try:
            data = None
            if isinstance(message, dict):
                data = message.get("data") or message.get("result") or message
            price = None
            # Data can be a dict (single row) or a list of rows (snapshot/delta)
            if isinstance(data, dict):
                lp = data.get("lastPrice") or data.get("lp") or data.get("price")
                if lp is not None:
                    try:
                        price = float(lp)
                    except Exception:
                        price = None
            elif isinstance(data, list) and data:
                row = data[-1] if isinstance(data[-1], dict) else data[0]
                if isinstance(row, dict):
                    lp = row.get("lastPrice") or row.get("lp") or row.get("price")
                    if lp is not None:
                        try:
                            price = float(lp)
                        except Exception:
                            price = None
            if price is not None:
                self._last_tick_time = time.time()
                if callable(on_ticker):
                    on_ticker(symbol, price, self._last_tick_time)
        except Exception as e:
            self.logger.debug(f"Ticker parse error for {symbol}: {e}")

    def _ensure_ws(self) -> bool:
        if WebSocket is None:
            return False
        try:
            self._ws = WebSocket(testnet=self.testnet, channel_type="spot")
            return True
        except Exception as e:
            self.logger.error(f"WebSocket init failed: {e}")
            self._ws = None
            return False

    def _resubscribe_all(self) -> None:
        if self._ws is None:
            return
        with self._lock:
            symbols = list(self._symbols)
            on_ticker = self._on_ticker
            on_orderbook = self._on_orderbook
            on_trade = self._on_trade
        for sym in symbols:
            try:
                self._ws.ticker_stream(callback=(lambda msg, s=sym: self._on_raw_ticker(msg, s, on_ticker)), symbol=sym)
            except Exception as e:
                self.logger.error(f"Resubscribe failed for {sym}: {e}")
            # attempt to resub orderbook/trades
            try:
                self._ws.orderbook_stream(callback=(lambda msg, s=sym: self._on_raw_orderbook(msg, s, on_orderbook)), symbol=sym, depth=50)  # type: ignore[attr-defined]
            except Exception:
                try:
                    self._ws.orderbook_50_stream(callback=(lambda msg, s=sym: self._on_raw_orderbook(msg, s, on_orderbook)), symbol=sym)  # type: ignore[attr-defined]
                except Exception:
                    pass
            try:
                self._ws.public_trade_stream(callback=(lambda msg, s=sym: self._on_raw_trade(msg, s, on_trade)), symbol=sym)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._last_tick_time = time.time()
        self.logger.info(f"Resubscribed to {len(symbols)} spot tickers")

    def _monitor_loop(self) -> None:
        backoff = self._base_backoff
        while not self._stop_event.is_set():
            try:
                stale = (time.time() - self._last_tick_time) > self._stale_seconds
                needs_reconnect = stale or self._ws is None
                if needs_reconnect:
                    self.logger.warning(
                        f"WS stale or closed. Reconnecting (backoff {backoff:.1f}s)..."
                    )
                    time.sleep(backoff * (0.5 + random.random()))  # jitter
                    if self._ensure_ws():
                        try:
                            self._resubscribe_all()
                            backoff = self._base_backoff
                        except Exception as e:
                            self.logger.error(f"Resubscribe error: {e}")
                            backoff = min(self._backoff_cap, max(self._base_backoff, backoff * 2))
                    else:
                        backoff = min(self._backoff_cap, max(self._base_backoff, backoff * 2))
                time.sleep(2.0)
            except Exception as e:
                self.logger.error(f"WS monitor error: {e}")
                time.sleep(2.0)

    def _on_raw_orderbook(self, message, symbol: str, on_orderbook: Optional[OrderbookCallback]) -> None:
        if not callable(on_orderbook):
            return
        try:
            data = None
            if isinstance(message, dict):
                data = message.get("data") or message.get("result") or message
            bids = []
            asks = []
            best_bid = None
            best_ask = None
            if isinstance(data, dict):
                b = data.get("b") or data.get("bid") or data.get("bids")
                a = data.get("a") or data.get("ask") or data.get("asks")
                if isinstance(b, list):
                    for row in b:
                        try:
                            price = float(row[0]) if isinstance(row, (list, tuple)) else float(row.get("price"))
                            qty = float(row[1]) if isinstance(row, (list, tuple)) else float(row.get("size"))
                            bids.append((price, qty))
                        except Exception:
                            continue
                if isinstance(a, list):
                    for row in a:
                        try:
                            price = float(row[0]) if isinstance(row, (list, tuple)) else float(row.get("price"))
                            qty = float(row[1]) if isinstance(row, (list, tuple)) else float(row.get("size"))
                            asks.append((price, qty))
                        except Exception:
                            continue
                if bids:
                    best_bid = bids[0][0]
                if asks:
                    best_ask = asks[0][0]
            if best_bid is not None and best_ask is not None:
                on_orderbook(symbol, best_bid, best_ask, bids, asks)
        except Exception as e:
            self.logger.debug(f"Orderbook parse error for {symbol}: {e}")

    def _on_raw_trade(self, message, symbol: str, on_trade: Optional[TradeCallback]) -> None:
        if not callable(on_trade):
            return
        try:
            data = None
            if isinstance(message, dict):
                data = message.get("data") or message.get("result") or message
            if isinstance(data, dict):
                rows = data.get("list") or data.get("data") or []
                if isinstance(rows, list):
                    for row in rows:
                        try:
                            p = float(row.get("p") or row.get("price"))
                            v = float(row.get("v") or row.get("size") or row.get("qty") or 0.0)
                            t = float(row.get("T") or row.get("ts") or 0.0)
                            on_trade(symbol, p, v, t)
                        except Exception:
                            continue
        except Exception as e:
            self.logger.debug(f"Trade parse error for {symbol}: {e}")

    def reconnect_on_failure(self) -> None:
        self.logger.info("Manual reconnection requested")
        self._last_tick_time = 0.0

    def stop(self) -> None:
        self._stop_event.set()
        # Best-effort: allow monitor thread to exit
        try:
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=3)
        except Exception:
            pass
        self._monitor_thread = None
        self._ws = None 