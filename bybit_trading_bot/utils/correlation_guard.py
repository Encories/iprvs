from __future__ import annotations

from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class CorrelationGuardConfig:
    lookback_points: int = 60  # use ~last 60 returns (e.g., M1 → 1h)
    min_points: int = 20
    block_threshold: float = 0.85
    block_window_seconds: int = 180  # 3 minutes window after opening a correlated long


class CorrelationGuard:
    def __init__(self, config: CorrelationGuardConfig) -> None:
        self.config = config
        self._returns: Dict[str, Deque[Tuple[float, float]]] = defaultdict(lambda: deque(maxlen=self.config.lookback_points))
        self._active_longs: Dict[str, float] = {}  # symbol -> opened_ts

    def update_price(self, symbol: str, ts_epoch: float, price: float) -> None:
        q = self._returns[symbol]
        if q and q[-1][0] < ts_epoch and q[-1][1] > 0:
            prev_price = q[-1][1]
            ret = (price - prev_price) / prev_price if prev_price > 0 else 0.0
            q.append((ts_epoch, ret))
        else:
            q.append((ts_epoch, price))

    def register_long(self, symbol: str, ts_epoch: float) -> None:
        self._active_longs[symbol] = ts_epoch

    def _pearson(self, a: Deque[Tuple[float, float]], b: Deque[Tuple[float, float]]) -> float:
        import math
        # Align by latest N min length and treat values as returns (second element)
        va = [x[1] for x in list(a)[-self.config.lookback_points :]]
        vb = [x[1] for x in list(b)[-self.config.lookback_points :]]
        n = min(len(va), len(vb))
        if n < self.config.min_points:
            return 0.0
        va = va[-n:]
        vb = vb[-n:]
        ma = sum(va) / n
        mb = sum(vb) / n
        num = sum((x - ma) * (y - mb) for x, y in zip(va, vb))
        da = math.sqrt(sum((x - ma) ** 2 for x in va)) or 1.0
        db = math.sqrt(sum((y - mb) ** 2 for y in vb)) or 1.0
        return max(-1.0, min(1.0, num / (da * db)))

    def ok(self, symbol: str, now_epoch: float) -> bool:
        # If no active longs, always OK
        if not self._active_longs:
            return True
        # Check block window against highly correlated active longs
        for s, opened_ts in self._active_longs.items():
            if now_epoch - opened_ts <= self.config.block_window_seconds:
                rho = self._pearson(self._returns[symbol], self._returns[s])
                if rho >= self.config.block_threshold:
                    return False
        return True


