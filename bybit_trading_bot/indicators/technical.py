from __future__ import annotations

from typing import List, Tuple

import numpy as np


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    if len(prices) < period + 1:
        return []
    arr = np.asarray(prices, dtype=float)
    diffs = np.diff(arr)
    ups = np.clip(diffs, 0, None)
    downs = -np.clip(diffs, None, 0)
    roll_up = np.convolve(ups, np.ones(period), 'valid') / period
    roll_down = np.convolve(downs, np.ones(period), 'valid') / period
    rs = np.divide(roll_up, np.where(roll_down == 0, np.nan, roll_down))
    rsi = 100 - (100 / (1 + rs))
    return rsi.tolist()


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float]]:
    if len(prices) < slow + signal:
        return [], []
    arr = np.asarray(prices, dtype=float)
    def ema(x: np.ndarray, span: int) -> np.ndarray:
        alpha = 2 / (span + 1)
        out = np.empty_like(x)
        out[0] = x[0]
        for i in range(1, len(x)):
            out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
        return out
    ema_fast = ema(arr, fast)
    ema_slow = ema(arr, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    return macd_line.tolist(), signal_line.tolist()


def calculate_relative_volume(volumes: List[float], period: int = 20) -> List[float]:
    if len(volumes) < period + 1:
        return []
    arr = np.asarray(volumes, dtype=float)
    rel = []
    for i in range(period, len(arr)):
        window = arr[i - period:i]
        avg = window.mean() if window.size > 0 else 0.0
        rel.append(0.0 if avg == 0 else float(arr[i] / avg))
    return rel
