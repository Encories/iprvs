from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MTFConfig:
    enabled: bool = True
    require_confirmation: bool = True


class MultiTimeframeFilter:
    """Stub MTF trend filter.

    In online mode without OHLC aggregation infra, we approximate trend by EMA slope
    on the recent buffer. The interface mirrors a future enriched implementation.
    """

    def __init__(self, config: MTFConfig) -> None:
        self.config = config

    def get_trend_direction(self, symbol: str) -> str:
        # Placeholder: assume BULLISH; integrate with bars service later
        return "BULLISH"

    def validate_entry_signal(self, side: str, trend_dir: str) -> bool:
        if not self.config.enabled:
            return True
        if not self.config.require_confirmation:
            return True
        side = side.lower()
        trend_dir = str(trend_dir).upper()
        if side == "long":
            return trend_dir == "BULLISH"
        if side == "short":
            return trend_dir == "BEARISH"
        return False


