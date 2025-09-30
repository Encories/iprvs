from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class VolumeConfig:
    obv_enabled: bool = True
    obv_trend_periods: int = 10
    volume_quality_check: bool = True


class VolumeSignalAnalyzer:
    def __init__(self, config: VolumeConfig) -> None:
        self.config = config

    def detect_volume_spike(self, volumes: List[float], lookback: int, spike_multiplier: float) -> float:
        if not volumes or len(volumes) < max(3, lookback + 1):
            return 0.0
        base = volumes[-(lookback + 1) : -1]
        if not base:
            return 0.0
        avg = sum(base) / len(base)
        if avg <= 0.0:
            return 0.0
        ratio = float(volumes[-1]) / avg
        return ratio if ratio >= float(spike_multiplier) else 0.0

    def calculate_obv_trend(self, prices: List[float], volumes: List[float]) -> float:
        if not self.config.obv_enabled:
            return 0.0
        n = max(3, int(self.config.obv_trend_periods))
        if not prices or not volumes or len(prices) != len(volumes) or len(prices) < n + 1:
            return 0.0
        obv: List[float] = [0.0]
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif prices[i] < prices[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        # EMA slope approximation over last n
        tail = obv[-n:]
        if len(tail) < 2:
            return 0.0
        x = list(range(len(tail)))
        mean_x = sum(x) / len(x)
        mean_y = sum(tail) / len(tail)
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, tail))
        den = sum((xi - mean_x) ** 2 for xi in x) or 1.0
        slope = num / den
        return float(slope)

    def validate_volume_quality(self, spike_ratio: float, obv_slope: float, price_dir: float) -> bool:
        if not self.config.volume_quality_check:
            return True
        # Basic consistency: need spike and obv slope in direction of price change
        if spike_ratio <= 0.0:
            return False
        if price_dir > 0 and obv_slope <= 0:
            return False
        if price_dir < 0 and obv_slope >= 0:
            return False
        return True


