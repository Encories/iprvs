from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from bybit_trading_bot.config.settings import Config
from bybit_trading_bot.utils.logger import get_logger
from bybit_trading_bot.utils.db_manager import DBManager, TradeRecord
from bybit_trading_bot.core.order_manager import OrderManager
from bybit_trading_bot.risk.atr_manager import ATRRiskManager, ATRConfig


@dataclass
class PositionState:
    tp1_price: float
    tp2_price: float
    tp1_size: float
    remainder_size: float
    be_sl_set: bool = False


class AdvancedPositionManager:
    """Manages partial take-profits, break-even SL, and optional ATR-based trailing for spot positions.

    For simplicity, state is kept in-memory; on process restart it will rebuild lazily on demand.
    """

    def __init__(self, config: Config, db: DBManager, order_manager: OrderManager, notifier) -> None:
        self.config = config
        self.db = db
        self.om = order_manager
        self.notifier = notifier
        self.logger = get_logger(self.__class__.__name__)
        try:
            self._atrm = ATRRiskManager(ATRConfig(period=int(self.config.atr_period), sl_multiplier=float(self.config.atr_sl_multiplier), trail_multiplier=float(self.config.atr_trail_multiplier), enabled=bool(self.config.atr_enabled)))
        except Exception:
            self._atrm = None
        # order_id -> PositionState
        self._state: Dict[str, PositionState] = {}

    def _compute_tp_prices(self, entry_price: float, atr: Optional[float]) -> tuple[float, float]:
        # TP1 percent
        try:
            tp1_pct = float(getattr(self.config, "tp1_percent", 0.012))
        except Exception:
            tp1_pct = 0.012
        tp2_pct = float(self.config.target_profit_pct)
        tp1_raw = entry_price * (1.0 + tp1_pct)
        if atr is not None:
            try:
                mp = float(getattr(self.config, "tp1_atr_multiplier", 1.5))
            except Exception:
                mp = 1.5
            atr_tp1 = entry_price + atr * mp
            tp1 = min(tp1_raw, atr_tp1)
        else:
            tp1 = tp1_raw
        tp2 = entry_price * (1.0 + tp2_pct)
        return (tp1, tp2)

    def setup_brackets_after_fill(self, symbol: str, entry_price: float, filled_qty: float, atr: Optional[float]) -> None:
        if filled_qty <= 0.0 or entry_price <= 0.0:
            return
        tp1, tp2 = self._compute_tp_prices(entry_price, atr)
        try:
            pct = float(getattr(self.config, "partial_close_percent", 0.5))
        except Exception:
            pct = 0.5
        tp1_size = max(0.0, min(1.0, pct)) * filled_qty
        remainder = max(0.0, filled_qty - tp1_size)
        # Place TP1 and TP2 as separate limit orders (best-effort)
        try:
            if tp1_size > 0.0:
                self.om.place_tp_limit(symbol, tp1_size, tp1)
            if remainder > 0.0:
                self.om.place_tp_limit(symbol, remainder, tp2)
        except Exception as e:
            self.logger.debug(f"Bracket placement error {symbol}: {e}")
        # Optional initial protective SL at break-even (later adjusted by BE rule)
        try:
            if getattr(self.config, "place_exchange_sl", False) and bool(self.config.break_even_enabled):
                r = float(self.config.fee_rate)
                be_price = entry_price * (1.0 + r) / max(1e-12, (1.0 - r))
                self.om.place_sl_stop_limit(symbol, remainder if remainder > 0 else tp1_size, be_price)
        except Exception as e:
            self.logger.debug(f"Initial BE SL error {symbol}: {e}")

    def monitor_once(self) -> None:
        """Lightweight monitor to enforce BE move after TP1 and optional simple trailing.

        We rely on price >= tp1 as a proxy that TP1 is (or about to be) filled; then set BE SL on remainder.
        """
        try:
            open_trades = self.db.get_open_trades()
            if not open_trades:
                return
            symbols_by_id = {rec.id: rec.spot_symbol for rec in self.db.get_active_symbols()}
            for tr in open_trades:
                symbol = symbols_by_id.get(tr.symbol_id)
                if not symbol:
                    continue
                last_price = self.db.get_last_price(tr.symbol_id)
                if last_price is None or tr.entry_price <= 0:
                    continue
                state = self._state.get(tr.order_id)
                if state is None:
                    # Build state from config on first encounter
                    atr = None
                    try:
                        if self._atrm is not None:
                            series = self.db.get_recent_price_series(tr.symbol_id, minutes=max(5, int(self.config.signal_window_minutes)))
                            vals = [p for (_, p) in series][- (self._atrm.config.period + 5):]
                            if len(vals) >= self._atrm.config.period + 1:
                                # simple pseudo OHLC: rolling chunks
                                highs = []
                                lows = []
                                closes = []
                                stride = max(1, len(vals) // (self._atrm.config.period + 1))
                                for i in range(0, len(vals), stride):
                                    ch = vals[i:i+stride]
                                    if not ch:
                                        continue
                                    highs.append(max(ch))
                                    lows.append(min(ch))
                                    closes.append(ch[-1])
                                atr = self._atrm.calculate_atr(highs, lows, closes)
                    except Exception:
                        atr = None
                    tp1, tp2 = self._compute_tp_prices(tr.entry_price, atr)
                    try:
                        pct = float(getattr(self.config, "partial_close_percent", 0.5))
                    except Exception:
                        pct = 0.5
                    tp1_size = tr.quantity * max(0.0, min(1.0, pct))
                    remainder = max(0.0, tr.quantity - tp1_size)
                    state = PositionState(tp1_price=tp1, tp2_price=tp2, tp1_size=tp1_size, remainder_size=remainder)
                    self._state[tr.order_id] = state
                # Break-even move after TP1
                if bool(getattr(self.config, "break_even_enabled", True)) and not state.be_sl_set and last_price >= state.tp1_price * 0.999:
                    try:
                        r = float(self.config.fee_rate)
                        be_price = tr.entry_price * (1.0 + r) / max(1e-12, (1.0 - r))
                        qty = max(0.0, tr.quantity - state.tp1_size)
                        if qty > 0.0:
                            self.om.place_sl_stop_limit(symbol, qty, be_price)
                            state.be_sl_set = True
                            self.logger.info(f"BE SL set: {symbol} qty={qty} trigger={be_price:.6f}")
                            try:
                                self.notifier.send_telegram(f"BE SL SET: {symbol} qty={qty} trigger={be_price:.6f}")
                            except Exception:
                                pass
                    except Exception as e:
                        self.logger.debug(f"BE move error {symbol}: {e}")
        except Exception as e:
            self.logger.error(f"AdvancedPositionManager monitor error: {e}")


