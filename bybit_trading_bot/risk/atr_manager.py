from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ATRConfig:
    period: int = 14
    sl_multiplier: float = 2.0
    trail_multiplier: float = 2.5
    enabled: bool = True


class ATRRiskManager:
    """ATR-based risk manager implementing TR/ATR, initial SL and trailing updates.

    This module is self-contained and does not depend on pandas for runtime ATR.
    """

    def __init__(self, config: ATRConfig) -> None:
        self.config = config

    @staticmethod
    def _true_range(high: float, low: float, prev_close: Optional[float]) -> float:
        if prev_close is None:
            return float(high - low)
        return float(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> Optional[float]:
        n = int(max(1, self.config.period))
        if not highs or not lows or not closes:
            return None
        if not (len(highs) == len(lows) == len(closes)):
            return None
        if len(highs) < n + 1:
            # need at least period+1 to compute first TR sequence with prev close
            return None
        trs: List[float] = []
        prev_close: Optional[float] = None
        for h, l, c in zip(highs, lows, closes):
            tr = self._true_range(float(h), float(l), prev_close)
            trs.append(tr)
            prev_close = float(c)
        # RMA (Wilder's) ATR
        # Initialize with SMA of first n TRs, then smooth
        if len(trs) < n:
            return None
        initial = sum(trs[:n]) / float(n)
        atr = initial
        alpha = 1.0 / float(n)
        for tr in trs[n:]:
            atr = atr + alpha * (tr - atr)
        return float(max(0.0, atr))

    def get_stop_loss_price(self, entry_price: float, atr: Optional[float], side: str) -> Optional[float]:
        if not self.config.enabled:
            return None
        if atr is None or entry_price <= 0.0:
            return None
        mult = float(self.config.sl_multiplier)
        if side.lower() == "long":
            return float(max(0.0, entry_price - mult * atr))
        elif side.lower() == "short":
            return float(max(0.0, entry_price + mult * atr))
        return None

    def update_trailing_stop(self, highest_price: float, atr: Optional[float]) -> Optional[float]:
        if not self.config.enabled:
            return None
        if atr is None or highest_price <= 0.0:
            return None
        mult = float(self.config.trail_multiplier)
        return float(max(0.0, highest_price - mult * atr))

    @staticmethod
    def build_ohlc_from_ticks(prices: List[Tuple[float, float]], window_sec: int) -> Optional[Tuple[float, float, float]]:
        """Utility: construct (high, low, close) from recent tick buffer [(ts, price), ...].

        Returns (high, low, close) or None if insufficient points.
        """
        if not prices:
            return None
        vals = [float(p) for (_, p) in prices[-max(2, min(len(prices), window_sec)) :]]
        if not vals:
            return None
        return (max(vals), min(vals), float(vals[-1]))


