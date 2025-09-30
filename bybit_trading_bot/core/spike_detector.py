from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Optional, Tuple

from bybit_trading_bot.config.settings import Config
from bybit_trading_bot.utils.logger import get_logger
from bybit_trading_bot.core.order_manager import OrderManager
from bybit_trading_bot.utils.db_manager import DBManager
from bybit_trading_bot.indicators.technical import calculate_rsi, calculate_macd, calculate_relative_volume
from bybit_trading_bot.risk.atr_manager import ATRRiskManager, ATRConfig
from bybit_trading_bot.utils.expectancy import expectancy, ExpectancyInputs


@dataclass
class SpikeSignal:
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    strength: float


class SpikeDetector:
    def __init__(self, config: Config, order_manager: Optional[OrderManager] = None, db: Optional[DBManager] = None) -> None:
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.buffer_size = 100
        self.price_buffer: Deque[float] = deque(maxlen=self.buffer_size)
        self.volume_buffer: Deque[float] = deque(maxlen=self.buffer_size)
        self.timestamp_buffer: Deque[datetime] = deque(maxlen=self.buffer_size)
        self.om = order_manager
        self.db = db
        # orderbook state
        self.best_bid: Optional[float] = None
        self.best_ask: Optional[float] = None
        self.last_imbalance: Optional[float] = None
        self.last_spread: Optional[float] = None
        # ATR risk manager (optional)
        try:
            self._atrm = ATRRiskManager(ATRConfig(period=int(self.config.atr_period), sl_multiplier=float(self.config.atr_sl_multiplier), trail_multiplier=float(self.config.atr_trail_multiplier), enabled=bool(self.config.atr_enabled)))
        except Exception:
            self._atrm = None
        # Diagnostics of last strength components
        self.last_strength: float = 0.0
        self.last_vol_spike_ratio: Optional[float] = None
        self.last_rsi: Optional[float] = None
        self.last_macd_hist: Optional[float] = None

    def initialize_buffers(self) -> None:
        self.price_buffer.clear()
        self.volume_buffer.clear()
        self.timestamp_buffer.clear()

    def update_market_data(self, price: float, volume: float, ts: datetime) -> None:
        self.price_buffer.append(float(price))
        self.volume_buffer.append(float(volume))
        self.timestamp_buffer.append(ts)

    def _volume_spike_ratio(self) -> Optional[float]:
        lookback = max(5, int(self.config.volume_lookback_periods))
        if len(self.volume_buffer) < lookback:
            return None
        recent = list(self.volume_buffer)
        base = recent[-lookback:][:-1]
        if not base:
            return None
        avg = sum(base) / len(base)
        last = recent[-1]
        if avg <= 0:
            return None
        return float(last) / float(avg)

    def detect_volume_spike(self) -> bool:
        ratio = self._volume_spike_ratio()
        return (ratio is not None) and (ratio >= float(self.config.volume_spike_multiplier))

    def calculate_signal_strength(self) -> float:
        strength = 0.0
        # Volume spike
        ratio = self._volume_spike_ratio()
        self.last_vol_spike_ratio = ratio
        if ratio is not None and ratio >= float(self.config.volume_spike_multiplier):
            strength += 0.5
        else:
            # Fallback: price impulse over a short window if trade volume stream is unavailable
            try:
                impulse_window = int(getattr(self.config, "split_impulse_window_sec", 15))
                impulse_bp = float(getattr(self.config, "split_impulse_min_bp", 15.0))  # basis points
                if impulse_window > 0 and impulse_bp > 0 and len(self.price_buffer) >= 3 and len(self.timestamp_buffer) >= 3:
                    now_ts = self.timestamp_buffer[-1].timestamp()
                    # find the oldest price within the window
                    idx = len(self.timestamp_buffer) - 1
                    while idx > 0 and (now_ts - self.timestamp_buffer[idx].timestamp()) <= impulse_window:
                        idx -= 1
                    p_old = self.price_buffer[max(0, idx)]
                    p_new = self.price_buffer[-1]
                    if p_old > 0:
                        ret = (p_new - p_old) / p_old
                        if ret >= (impulse_bp / 10000.0):
                            strength += 0.5
            except Exception:
                pass
        prices = list(self.price_buffer)
        self.last_rsi = None
        self.last_macd_hist = None
        if len(prices) >= max(26, self.config.rsi_period + 1):
            rsi = calculate_rsi(prices, period=self.config.rsi_period)
            if rsi:
                try:
                    self.last_rsi = float(rsi[-1])
                except Exception:
                    self.last_rsi = None
                if self.last_rsi is not None and (self.last_rsi < float(self.config.rsi_overbought)):
                    strength += 0.25
            macd_line, signal_line = calculate_macd(prices, fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal)
            if macd_line and signal_line:
                try:
                    self.last_macd_hist = float(macd_line[-1] - signal_line[-1])
                except Exception:
                    self.last_macd_hist = None
                if self.last_macd_hist is not None and self.last_macd_hist > 0:
                    strength += 0.25
        # orderbook contribution
        if self.last_imbalance is not None and self.last_spread is not None:
            if self.last_imbalance >= float(self.config.orderbook_imbalance_threshold) and self.last_spread <= float(self.config.bid_ask_spread_threshold):
                strength = min(1.0, strength + 0.15)
        self.last_strength = float(min(1.0, strength))
        return self.last_strength

    def update_orderbook(self, best_bid: float, best_ask: float, bids: Optional[list] = None, asks: Optional[list] = None, levels: int = 5) -> None:
        self.best_bid = best_bid
        self.best_ask = best_ask
        try:
            spread = 0.0 if best_ask <= 0 else (best_ask - best_bid) / best_ask
            self.last_spread = spread
            imb = None
            if bids and asks:
                bvol = sum(float(q) for _, q in bids[:levels]) if bids else 0.0
                avol = sum(float(q) for _, q in asks[:levels]) if asks else 0.0
                denom = (bvol + avol)
                imb = (bvol - avol) / denom if denom > 0 else 0.0
            self.last_imbalance = imb
        except Exception:
            pass

    def generate_trading_signal(self, symbol: str) -> Optional[SpikeSignal]:
        if not self.price_buffer:
            return None
        strength = self.calculate_signal_strength()
        if strength < float(self.config.split_min_signal_strength):
            return None
        return SpikeSignal(
            symbol=symbol,
            price=self.price_buffer[-1],
            volume=self.volume_buffer[-1] if self.volume_buffer else 0.0,
            timestamp=self.timestamp_buffer[-1] if self.timestamp_buffer else datetime.utcnow(),
            strength=strength,
        )

    def execute_signal(self, signal: SpikeSignal) -> Optional[str]:
        if self.om is None:
            self.logger.warning("OrderManager not set for SpikeDetector")
            return None
        try:
            # Position size from TRADE_NOTIONAL_USDT
            if signal.price <= 0.0:
                return None
            qty = (self.config.trade_notional_usdt or 0.0) / signal.price
            if qty <= 0:
                return None
            # Dynamic OFFSET: max(κ_vol·σ_1m, κ_spread·spread, min_tick*N) with imbalance adjustment
            try:
                offset = float(self.config.limit_order_offset)
                if getattr(self.config, "dynamic_offset_enabled", False):
                    # approximate 1m volatility via last 60 prices stddev
                    import math
                    prices = list(self.price_buffer)
                    vol_sigma = 0.0
                    if len(prices) >= 10:
                        tail = prices[-min(len(prices), 60):]
                        m = sum(tail) / len(tail)
                        var = sum((p - m) ** 2 for p in tail) / max(1, (len(tail) - 1))
                        vol_sigma = math.sqrt(max(0.0, var)) / max(1e-12, m)
                    spread = 0.0
                    if self.best_bid is not None and self.best_ask is not None and self.best_ask > 0:
                        spread = (self.best_ask - self.best_bid) / self.best_ask
                    base = max(float(self.config.offset_vol_k) * vol_sigma, float(self.config.offset_spread_k) * spread, 0.00025)
                    adj = 0.0
                    if self.last_imbalance is not None and self.last_imbalance > 0.4:
                        adj = -0.15 * base
                    offset = min(0.006, max(0.0025, base + adj))
                entry_price = signal.price * (1.0 - offset)
            except Exception:
                entry_price = signal.price * (1.0 - float(self.config.limit_order_offset))
            resp = self.om.place_limit_order(signal.symbol, "Buy", qty, entry_price)
            if not resp:
                return None
            order_id = str(resp.get("orderId") or resp.get("result", {}).get("orderId") or "")
            if not order_id:
                return None
            # Wait for fill then place TP (+ target_profit_pct)
            row = self.om.wait_for_filled(order_id, timeout_s=float(self.config.order_timeout_seconds))
            if row and str(row.get("orderStatus", "")).lower() == "filled":
                # Compute ATR-based SL percent if enabled
                sl_pct = 0.0
                try:
                    if self._atrm is not None and bool(self.config.dynamic_sl_enabled):
                        # Build quick OHLC from internal buffers as approximation for ATR window (e.g., 5m)
                        highs: list[float] = []
                        lows: list[float] = []
                        closes: list[float] = []
                        prices = list(self.price_buffer)
                        if len(prices) >= max(20, self._atrm.config.period + 2):
                            # naive slice-based OHLC aggregation
                            stride = max(1, len(prices) // (self._atrm.config.period + 1))
                            for i in range(0, len(prices), stride):
                                chunk = prices[i : i + stride]
                                if not chunk:
                                    continue
                                highs.append(max(chunk))
                                lows.append(min(chunk))
                                closes.append(chunk[-1])
                            atr = self._atrm.calculate_atr(highs, lows, closes)
                            try:
                                entry = float(row.get("avgPrice") or row.get("price") or entry_price)
                            except Exception:
                                entry = entry_price
                            if atr is not None and entry > 0.0:
                                sl_abs = self._atrm.get_stop_loss_price(entry, atr, side="long")
                                if sl_abs is not None and sl_abs > 0.0:
                                    sl_pct = max(0.0, (entry - sl_abs) / entry)
                except Exception:
                    sl_pct = 0.0
                # Gate by expectancy using heuristic TP-hit probability (reuse strength as proxy)
                try:
                    p_hit = min(1.0, max(0.0, float(self.config.tp_prob_threshold) * (0.9 + 0.2 * strength)))
                    exp = expectancy(ExpectancyInputs(p_hit=p_hit, tp_pct=float(self.config.target_profit_pct), sl_pct=sl_pct, fee_rate=float(self.config.fee_rate), slip_pct=0.0005))
                    if exp <= 0.0:
                        # If expectancy negative, immediately cancel TP and close at market (avoid bad fills)
                        try:
                            # place immediate close
                            self.om.close_position_market(signal.symbol, float(row.get("cumExecQty") or row.get("qty") or 0.0))
                        except Exception:
                            pass
                        return order_id
                except Exception:
                    pass
                # Set up partial TP and BE/trailing via AdvancedPositionManager-like brackets
                try:
                    entry = float(row.get("avgPrice") or row.get("price") or entry_price)
                    qty = float(row.get("cumExecQty") or row.get("qty") or 0.0)
                except Exception:
                    entry = entry_price
                    qty = float(row.get("qty") or 0.0)
                # Metrics: log slippage vs limit entry price
                try:
                    if entry_price > 0:
                        slippage_bp = (entry - entry_price) / entry_price * 10000.0
                        self.logger.info(f"Split fill slippage: {signal.symbol} {slippage_bp:.1f} bp (limit {entry_price:.6f}, avg {entry:.6f})")
                except Exception:
                    pass
                # Mark split order row as filled if DB available
                try:
                    if self.db is not None:
                        self.db.update_sp_order_filled(order_id)
                except Exception:
                    pass
                # Fallback: still place a simple full TP if advanced logic fails
                try:
                    from bybit_trading_bot.position.manager import AdvancedPositionManager  # lazy import
                    atr_val = None
                    if self._atrm is not None:
                        atr_val = None  # ATR approximated earlier; keep None to avoid heavy calc here
                    # We don't have a shared instance here; use OM directly for bracket placement
                    # compute TP1/TP2 and place two limits
                    tp2_price = entry * (1.0 + float(self.config.target_profit_pct))
                    tp1_pct = float(getattr(self.config, "tp1_percent", 0.012))
                    tp1_price = min(entry * (1.0 + tp1_pct), entry + (atr_val or 0.0) * float(getattr(self.config, "tp1_atr_multiplier", 1.5))) if atr_val is not None else entry * (1.0 + tp1_pct)
                    part = max(0.0, min(1.0, float(getattr(self.config, "partial_close_percent", 0.5))))
                    tp1_qty = qty * part
                    tp2_qty = max(0.0, qty - tp1_qty)
                    if tp1_qty > 0.0:
                        self.om.place_tp_limit(signal.symbol, tp1_qty, tp1_price)
                    if tp2_qty > 0.0:
                        self.om.place_tp_limit(signal.symbol, tp2_qty, tp2_price)
                except Exception:
                    self.om.post_fill_tp_sl(signal.symbol, row, tp_pct=float(self.config.target_profit_pct), sl_pct=sl_pct)
                return order_id
            # timeout — cancel the order
            try:
                self.om.cancel_order(signal.symbol, order_id)
            except Exception:
                pass
            return order_id
        except Exception as e:
            self.logger.error(f"execute_signal error: {e}")
            return None
